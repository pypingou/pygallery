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

# NEW: Function to scan and generate all missing thumbnails at startup
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
    Returns a JSON list of all albums by scanning the PHOTOS_DIR on demand.
    Thumbnails are assumed to be mostly pre-generated.
    """
    print(f"\n--- API albums requested (RUNTIME) ---")
    print(f"Request URL: {request.url}")
    print(f"Request base_url: {request.base_url}")
    print(f"Request url_root: {request.url_root}")
    print(f"Request script_root: {request.script_root}") # This should be the prefix or '/'
    print(f"request.environ['SERVER_NAME']: {request.environ.get('SERVER_NAME')}")
    print(f"request.environ['SERVER_PORT']: {request.environ.get('SERVER_PORT')}")
    print(f"request.environ['wsgi.url_scheme']: {request.environ.get('wsgi.url_scheme')}")
    print(f"os.environ SCRIPT_NAME (from Docker/Quadlet): {os.environ.get('SCRIPT_NAME')}") # What Gunicorn gets
    print(f"PHOTOS_DIR: {app_config['PHOTOS_DIR']}")
    
    albums_list = []
    photos_root = app_config['PHOTOS_DIR']
    thumbnail_size = app_config['THUMBNAIL_SIZE']

    if not photos_root.is_dir():
        print(f"Error: PHOTOS_DIR '{photos_root}' does not exist or is not a directory. Returning empty albums.")
        return jsonify([])

    found_albums_data = {} # {album_path_str: {"cover_url": "", "photo_count": 0}}

    try:
        for dirpath, dirnames, filenames in os.walk(photos_root):
            current_dir_images = [f for f in filenames if is_image_file(f)]
            
            if current_dir_images: # Only consider directories that contain images as albums
                try:
                    relative_path = Path(dirpath).relative_to(photos_root)
                    album_name_key = str(relative_path).replace(os.sep, '/') # Use '/' for consistent keys

                    # Sort images to find the first one for cover if needed
                    current_dir_images.sort(key=lambda x: x.lower())
                    first_image_filename = current_dir_images[0]
                    
                    # Ensure thumbnail for cover image exists (on-demand generation)
                    album_thumbnail_dir = app_config['THUMBNAILS_DIR'] / relative_path
                    cover_image_path = Path(dirpath) / first_image_filename
                    cover_thumbnail_path = album_thumbnail_dir / first_image_filename

                    get_or_create_thumbnail(cover_image_path, cover_thumbnail_path, thumbnail_size)

                    # Construct the internal URL for the cover thumbnail
                    # Use _external=True to generate absolute URLs based on the current request context
                    # Correct filename construction for url_for to handle root album
                    serve_filename_for_url = first_image_filename if album_name_key == '.' else f"{album_name_key}/{first_image_filename}"
                    
                    cover_thumbnail_url = url_for('gallery.serve_thumbnail', filename=serve_filename_for_url, _external=True)
                    print(f"  Generated URL for {album_name_key} cover: {cover_thumbnail_url}")

                    # NEW: Map '.' to '__root__' for external facing album name
                    album_name_for_url = '__root__' if album_name_key == '.' else album_name_key

                    found_albums_data[album_name_key] = {
                        "name": album_name_for_url, # Use '__root__' for URL and client-side logic
                        "display_name": album_name_key if album_name_key != '.' else 'Root Gallery',
                        "cover_thumbnail_url": cover_thumbnail_url,
                        "photo_count": len(current_dir_images)
                    }
                    print(f"  Found album: {album_name_key} with {len(current_dir_images)} photos.")
                except Exception as e:
                    print(f"Error processing album directory {dirpath}: {e}")
                    import traceback
                    traceback.print_exc()
        print(f"Finished os.walk for {photos_root}")
    except Exception as e:
        print(f"Unhandled error during os.walk on {photos_root}: {e}")
        import traceback
        traceback.print_exc()

    # Convert found_albums_data to a list and sort
    albums_list = list(found_albums_data.values())
    albums_list.sort(key=lambda x: x['display_name'].lower())
    
    print(f"API albums response: Found {len(albums_list)} albums.")
    return jsonify(albums_list)


@gallery_bp.route('/api/album/<path:album_name>')
def api_album_photos(album_name):
    """
    Returns a JSON list of photos for a specific album by scanning the directory.
    This is now done on demand for each API request.
    """
    print(f"\n--- API photos requested for album: {album_name} (RUNTIME) ---")
    print(f"Request URL: {request.url}")
    print(f"Request base_url: {request.base_url}")
    print(f"Request script_root: {request.script_root}")
    print(f"Request url_root: {request.url_root}")
    
    album_photos_list = []
    photos_root = app_config['PHOTOS_DIR']
    thumbnails_root = app_config['THUMBNAILS_DIR']
    thumbnail_size = app_config['THUMBNAIL_SIZE']

    # NEW: Map '__root__' back to '.' for file system access
    album_name_fs = '.' if album_name == '__root__' else album_name

    # Resolve the full path to the specific album directory on disk
    album_dir_path = photos_root / album_name_fs
    album_thumbnail_dir = thumbnails_root / album_name_fs

    if not album_dir_path.is_dir():
        print(f"API photos for album '{album_name}': Album directory not found or not a directory: {album_dir_path}")
        return jsonify({"error": "Album not found"}), 404

    try:
        for photo_filename in os.listdir(album_dir_path):
            photo_path = album_dir_path / photo_filename
            if photo_path.is_file() and is_image_file(photo_filename):
                thumbnail_path = album_thumbnail_dir / photo_filename

                get_or_create_thumbnail(photo_path, thumbnail_path, thumbnail_size) # On-demand thumbnail creation

                # Construct URLs (absolute using _external=True)
                # url_for needs filename to be relative to the PHOTOS_DIR/THUMBNAILS_DIR root
                serve_filename_for_url = photo_filename if album_name_fs == '.' else f"{album_name_fs}/{photo_filename}"
                original_url = url_for('gallery.serve_photo', filename=serve_filename_for_url, _external=True)
                thumb_url = url_for('gallery.serve_thumbnail', filename=serve_filename_for_url, _external=True)
                print(f"  Generated URL for {photo_filename} thumbnail: {thumb_url}")

                album_photos_list.append({
                    "original_filename": photo_filename,
                    "original_url": original_url,
                    "thumbnail_url": thumb_url
                })
        album_photos_list.sort(key=lambda x: x['original_filename'].lower())
        print(f"API photos for album '{album_name}': Found {len(album_photos_list)} photos.")
        return jsonify(album_photos_list)
    except Exception as e:
        print(f"Error listing photos in album {album_name}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Error processing album photos"}), 500


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

