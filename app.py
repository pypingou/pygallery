# app.py
import os
import configparser
from flask import Flask, render_template, send_from_directory, jsonify, Blueprint, url_for, request
from PIL import Image
from pathlib import Path
import threading
import time
from werkzeug.middleware.proxy_fix import ProxyFix # Import ProxyFix

# --- Configuration ---
app_config = {}

def load_config():
    """Loads configuration from config.ini."""
    global app_config
    config_file = 'config.ini'
    if not os.path.exists(config_file):
        print(f"Error: Configuration file '{config_file}' not found.")
        print("Please create a config.ini with [Gallery] section and PHOTOS_DIR, THUMBNAILS_DIR, THUMBNAIL_SIZE, PORT.")
        exit(1)

    config = configparser.ConfigParser()
    config.read(config_file)

    if 'Gallery' not in config:
        print(f"Error: 'Gallery' section not found in '{config_file}'.")
        exit(1)

    try:
        app_config['PHOTOS_DIR'] = Path(config['Gallery'].get('PHOTOS_DIR', './photos')).resolve()
        app_config['THUMBNAILS_DIR'] = Path(config['Gallery'].get('THUMBNAILS_DIR', './thumbnails')).resolve()
        app_config['THUMBNAIL_SIZE'] = tuple(map(int, config['Gallery'].get('THUMBNAIL_SIZE', '200,200').split(',')))
        app_config['PORT'] = int(config['Gallery'].get('PORT', '5000'))
    except ValueError as e:
        print(f"Error parsing configuration: {e}")
        exit(1)

    print(f"Configuration loaded: {app_config}")

# Load configuration when the script starts
load_config()

# Initialize Flask app - it will internally run at root '/'
app = Flask(__name__)

# --- Apply ProxyFix to the Flask application ---
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_prefix=1, x_proto=1)

# --- Create a Blueprint for the gallery ---
gallery_bp = Blueprint('gallery', __name__,
                       template_folder='templates',
                       static_folder='static', # Refers to the 'static' directory relative to app.py
                       static_url_path='/static') # This makes the blueprint's static files available at /static relative to its own root

# --- Image Handling Logic ---
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp')

def is_image_file(filename):
    """Checks if a file has a supported image extension."""
    return filename.lower().endswith(IMAGE_EXTENSIONS)

def get_or_create_thumbnail(image_path: Path, thumbnail_path: Path, size: tuple):
    """
    Generates a thumbnail for an image if it doesn't already exist.
    """
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    if thumbnail_path.exists():
        return # Thumbnail already exists
    
    try:
        with Image.open(image_path) as img:
            img.thumbnail(size)
            img.save(thumbnail_path)
    except Exception as e:
        print(f"Error generating thumbnail for {image_path}: {e}")

# Function to scan and generate all missing thumbnails at startup
def scan_and_generate_all_thumbnails():
    """
    Scans the PHOTOS_DIR for all images and generates missing thumbnails.
    This runs at application startup.
    """
    print(f"--- Starting initial thumbnail generation scan for '{app_config['PHOTOS_DIR']}' ---")
    photos_root = app_config['PHOTOS_DIR']
    thumbnails_root = app_config['THUMBNAILS_DIR']
    thumbnail_size = app_config['THUMBNAIL_SIZE']

    if not photos_root.is_dir():
        print(f"Warning: PHOTOS_DIR '{photos_root}' does not exist or is not a directory. Skipping initial thumbnail scan.")
        return

    thumbnails_root.mkdir(parents=True, exist_ok=True) # Ensure root thumbnail dir exists

    for dirpath, dirnames, filenames in os.walk(photos_root):
        current_dir_images = [f for f in filenames if is_image_file(f)]
        
        if current_dir_images:
            relative_path = Path(dirpath).relative_to(photos_root)
            album_thumbnail_dir = thumbnails_root / relative_path
            album_thumbnail_dir.mkdir(parents=True, exist_ok=True) # Ensure album thumbnail dir exists

            for photo_filename in current_dir_images:
                photo_path = Path(dirpath) / photo_filename
                thumbnail_path = album_thumbnail_dir / photo_filename
                
                # Only call get_or_create_thumbnail if it's a file and not already a thumbnail
                if photo_path.is_file():
                    get_or_create_thumbnail(photo_path, thumbnail_path, thumbnail_size)
    print("--- Initial thumbnail generation scan complete ---")


# NEW: Helper to list photos for a given filesystem path.
def _get_photos_for_fs_path(fs_path: Path, album_name_for_url: str):
    """
    Helper to list photos for a given filesystem path and construct their URLs.
    album_name_for_url is the name used in Flask URL routing (e.g., '__root__' or 'folder/sub').
    """
    photos_list = []
    thumbnail_size = app_config['THUMBNAIL_SIZE']
    photos_root = app_config['PHOTOS_DIR'] # Needed for relative_to in url_for filename

    if not fs_path.is_dir():
        print(f"DEBUG: _get_photos_for_fs_path: Filesystem path not found or not a directory: {fs_path}")
        return []

    try:
        for photo_filename in os.listdir(fs_path):
            photo_path = fs_path / photo_filename
            if photo_path.is_file() and is_image_file(photo_filename):
                # Construct thumbnail path
                relative_to_photos_root = photo_path.relative_to(photos_root)
                thumbnail_path = app_config['THUMBNAILS_DIR'] / relative_to_photos_root
                
                get_or_create_thumbnail(photo_path, thumbnail_path, thumbnail_size)

                # Determine the filename argument for url_for (relative to PHOTOS_DIR/THUMBNAILS_DIR)
                # This will be the full path e.g. 'image.jpg' or 'USA/image.jpg'
                filename_for_url_arg = str(relative_to_photos_root).replace(os.sep, '/')

                original_url = url_for('gallery.serve_photo', filename=filename_for_url_arg, _external=True)
                thumb_url = url_for('gallery.serve_thumbnail', filename=filename_for_url_arg, _external=True)

                photos_list.append({
                    "original_filename": photo_filename,
                    "original_url": original_url,
                    "thumbnail_url": thumb_url
                })
        photos_list.sort(key=lambda x: x['original_filename'].lower())
        print(f"DEBUG: _get_photos_for_fs_path: Found {len(photos_list)} photos in {fs_path}")
        return photos_list
    except Exception as e:
        print(f"Error in _get_photos_for_fs_path for {fs_path}: {e}")
        import traceback
        traceback.print_exc()
        return []


# --- API Endpoints ---

@gallery_bp.route('/')
def index():
    """Serves the main gallery page."""
    return render_template('index.html')

@gallery_bp.route('/album/<path:album_name>')
def album_page(album_name):
    """Serves a specific album page."""
    return render_template('album.html', album_name=album_name)

@gallery_bp.route('/api/albums')
def api_albums():
    """
    Returns a JSON response indicating gallery mode (flat or nested) and album/photo data.
    """
    print(f"\n--- API albums requested (RUNTIME) ---")
    print(f"Request URL: {request.url}")
    print(f"Request script_root: {request.script_root}")
    print(f"PHOTOS_DIR: {app_config['PHOTOS_DIR']}")
    
    albums_list = []
    photos_root = app_config['PHOTOS_DIR']
    
    # NEW: Read GALLERY_MODE from environment variable
    gallery_mode = os.environ.get('GALLERY_MODE', 'ALBUM_DISPLAY') # Default to album display

    if not photos_root.is_dir():
        print(f"Error: PHOTOS_DIR '{photos_root}' does not exist or is not a directory. Returning empty response.")
        return jsonify({"mode": "nested_gallery", "albums": []})

    # Determine if it's a flat gallery (only root photos, no sub-albums with photos)
    is_flat_gallery = False
    root_photos_count = 0
    nested_albums_count = 0

    # Walk through the directories to count photos and albums
    # Use topdown=True to allow modification of dirnames if needed, though not doing so here.
    for dirpath, dirnames, filenames in os.walk(photos_root, topdown=True):
        current_dir_images = [f for f in filenames if is_image_file(f)]
        
        if Path(dirpath) == photos_root: # Root directory
            root_photos_count = len(current_dir_images)
            # print(f"DEBUG: Root photos count: {root_photos_count}") # For debugging
        elif current_dir_images: # Any subdirectory with images
            nested_albums_count += 1
            # print(f"DEBUG: Found images in subdirectory: {dirpath}") # For debugging
    
    # Define flat gallery criteria: photos in root, and no other image-containing subdirectories
    if root_photos_count > 0 and nested_albums_count == 0:
        is_flat_gallery = True

    # --- Conditional Response based on GALLERY_MODE ---
    if gallery_mode == 'FLAT_ROOT_DISPLAY' and is_flat_gallery:
        print(f"Detected FLAT_ROOT_DISPLAY mode. Serving root photos directly.")
        root_photos_data = _get_photos_for_fs_path(photos_root, '__root__') # Get data for root photos
        return jsonify({"mode": "flat_gallery", "photos": root_photos_data})
    else:
        print(f"Detected NESTED_GALLERY mode or FLAT_ROOT_DISPLAY disabled. Serving album list.")
        # Rebuild albums_list logic for nested/default display
        found_albums_data = {}
        for dirpath, dirnames, filenames in os.walk(photos_root):
            current_dir_images = [f for f in filenames if is_image_file(f)]
            
            if current_dir_images:
                try:
                    relative_path = Path(dirpath).relative_to(photos_root)
                    album_name_key = str(relative_path).replace(os.sep, '/')

                    first_image_filename = current_dir_images[0]
                    album_thumbnail_dir = app_config['THUMBNAILS_DIR'] / relative_path
                    cover_image_path = Path(dirpath) / first_image_filename
                    cover_thumbnail_path = album_thumbnail_dir / first_image_filename
                    get_or_create_thumbnail(cover_image_path, cover_thumbnail_path, app_config['THUMBNAIL_SIZE'])

                    # Correct filename construction for url_for to handle root album
                    serve_filename_for_url = first_image_filename if album_name_key == '.' else f"{album_name_key}/{first_image_filename}"
                    cover_thumbnail_url = url_for('gallery.serve_thumbnail', filename=serve_filename_for_url, _external=True)
                    
                    # Map '.' to '__root__' for external facing album name
                    album_name_for_url = '__root__' if album_name_key == '.' else album_name_key

                    found_albums_data[album_name_key] = {
                        "name": album_name_for_url,
                        "display_name": album_name_key if album_name_key != '.' else 'Root Gallery',
                        "cover_thumbnail_url": cover_thumbnail_url,
                        "photo_count": len(current_dir_images)
                    }
                except Exception as e:
                    print(f"Error processing album directory {dirpath}: {e}")
                    import traceback
                    traceback.print_exc()
        
        albums_list = list(found_albums_data.values())
        albums_list.sort(key=lambda x: x['display_name'].lower())
        
        print(f"API albums response: Found {len(albums_list)} albums in nested mode.")
        return jsonify({"mode": "nested_gallery", "albums": albums_list})


# Main API endpoint for nested albums (e.g., /api/album/Family/Vacation/Paris/photos)
@gallery_bp.route('/api/album/<path:album_name>/photos')
def api_album_photos_nested(album_name):
    """
    Returns photos for nested albums. This endpoint explicitly expects '/photos' suffix.
    """
    print(f"--- API photos requested for album: {album_name} (RUNTIME - Nested) ---")
    # Call helper with the actual album_name (e.g., 'Family/Vacation/Paris')
    return _get_photos_for_fs_path(app_config['PHOTOS_DIR'] / album_name, album_name)


# NEW: Specific API endpoint for the root album (e.g., /api/album/__root__)
@gallery_bp.route('/api/album/__root__')
def api_album_photos_root():
    """
    Returns photos for the special '__root__' album.
    This endpoint handles requests without the '/photos' suffix for the root.
    """
    print(f"--- API photos requested for album: __root__ (RUNTIME - Root) ---")
    return _get_photos_for_fs_path(app_config['PHOTOS_DIR'], '__root__') # Call helper with PHOTOS_DIR root and special name


@gallery_bp.route('/photos/<path:filename>')
def serve_photo(filename):
    """Serves original photo files. Filename now includes album subpaths."""
    # This route expects filename to be the full path relative to app_config['PHOTOS_DIR']
    # e.g., 'image.jpg' or 'USA/2010/10/image.jpg'
    full_photo_path_in_root = app_config['PHOTOS_DIR'] / filename

    if not full_photo_path_in_root.is_file():
        print(f"Serve photo: File not found - {full_photo_path_in_root}")
        return "Photo not found", 404

    directory_to_serve_from = full_photo_path_in_root.parent
    file_base_name = full_photo_path_in_root.name
    print(f"Serving photo: {full_photo_path_in_root}")
    return send_from_directory(directory_to_serve_from, file_base_name)

@gallery_bp.route('/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    """Serves generated thumbnail files. Filename now includes album subpaths."""
    # This route expects filename to be the full path relative to app_config['THUMBNAILS_DIR']
    full_thumbnail_path_in_root = app_config['THUMBNAILS_DIR'] / filename

    if not full_thumbnail_path_in_root.is_file():
        print(f"Serve thumbnail: File not found - {full_thumbnail_path_in_root}")
        return "Thumbnail not found", 404

    directory_to_serve_from = full_thumbnail_path_in_root.parent
    file_base_name = full_thumbnail_path_in_root.name
    print(f"Serving thumbnail: {full_thumbnail_path_in_root}")
    return send_from_directory(directory_to_serve_from, file_base_name)

# Register the blueprint with the main Flask application.
app.register_blueprint(gallery_bp)


# --- Main execution ---
if __name__ == '__main__':
    # Ensure root photo and thumbnail directories exist
    app_config['PHOTOS_DIR'].mkdir(parents=True, exist_ok=True)
    app_config['THUMBNAILS_DIR'].mkdir(parents=True, exist_ok=True)

    # For local development, simulate the SCRIPT_NAME and SERVER_NAME
    # that Gunicorn/Apache would provide in a deployed environment.
    # This allows url_for to generate correct URLs.
    os.environ['SCRIPT_NAME'] = os.environ.get('SCRIPT_NAME', '/') # Internal root
    os.environ['SERVER_NAME'] = os.environ.get('SERVER_NAME', 'localhost')
    os.environ['SERVER_PORT'] = os.environ.get('SERVER_PORT', str(app_config['PORT']))
    os.environ['wsgi.url_scheme'] = os.environ.get('wsgi.url_scheme', 'http') # Default to http for local

    # Call the initial thumbnail generation scan at startup
    # This runs within a dummy request context so url_for works for local scan_and_generate_all_thumbnails calls.
    with app.test_request_context(
        path=os.environ['SCRIPT_NAME'], # Path is the app's root, e.g., '/'
        base_url=f"{os.environ['wsgi.url_scheme']}://{os.environ['SERVER_NAME']}:{os.environ['SERVER_PORT']}"
    ):
        request.environ['SCRIPT_NAME'] = os.environ['SCRIPT_NAME'] # Ensure SCRIPT_NAME is set
        scan_and_generate_all_thumbnails() # This function now just generates thumbnails

    print(f"Starting Flask app on {os.environ.get('wsgi.url_scheme', 'http')}://{os.environ.get('SERVER_NAME', 'localhost')}:{os.environ.get('SERVER_PORT', '5000')}{os.environ.get('SCRIPT_NAME', '/')}")
    app.run(host='0.0.0.0', port=app_config['PORT'], debug=True)

