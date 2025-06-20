# app.py
import os
import configparser
from flask import Flask, render_template, send_from_directory, jsonify, Blueprint
from PIL import Image
from pathlib import Path
import threading
import time

# --- Configuration ---
# Use a global variable for configuration to make it accessible across the app.
# This will be populated from config.ini.
app_config = {}

def load_config():
    """Loads configuration from config.ini."""
    global app_config
    config_file = 'config.ini'
    if not os.path.exists(config_file):
        print(f"Error: Configuration file '{config_file}' not found.")
        print("Please create a config.ini with [Gallery] section and PHOTOS_DIR, THUMBNAILS_DIR, THUMBNAIL_SIZE, PORT, BASE_URL_PREFIX.")
        exit(1)

    config = configparser.ConfigParser()
    config.read(config_file)

    if 'Gallery' not in config:
        print(f"Error: 'Gallery' section not found in '{config_file}'.")
        exit(1)

    try:
        app_config['PHOTOS_DIR'] = config['Gallery'].get('PHOTOS_DIR', './photos')
        app_config['THUMBNAILS_DIR'] = config['Gallery'].get('THUMBNAILS_DIR', './thumbnails')
        app_config['THUMBNAIL_SIZE'] = tuple(map(int, config['Gallery'].get('THUMBNAIL_SIZE', '200,200').split(',')))
        app_config['PORT'] = int(config['Gallery'].get('PORT', '5000'))
        # New: Base URL Prefix
        app_config['BASE_URL_PREFIX'] = config['Gallery'].get('BASE_URL_PREFIX', '/gallery').strip('/') # Remove trailing/leading slashes
        if app_config['BASE_URL_PREFIX']:
            app_config['BASE_URL_PREFIX'] = '/' + app_config['BASE_URL_PREFIX'] # Ensure it starts with a single slash
        else:
            app_config['BASE_URL_PREFIX'] = '' # For root deployment

    except ValueError as e:
        print(f"Error parsing configuration: {e}")
        exit(1)

    # Ensure paths are absolute for safety, or relative to the app's root
    app_config['PHOTOS_DIR'] = Path(app_config['PHOTOS_DIR']).resolve()
    app_config['THUMBNAILS_DIR'] = Path(app_config['THUMBNAILS_DIR']).resolve()

    print(f"Configuration loaded: {app_config}")

# Load configuration when the script starts
load_config()

# Initialize Flask app after config is loaded
app = Flask(__name__)

# --- Create a Blueprint for the gallery with a configurable URL prefix ---
gallery_bp = Blueprint('gallery', __name__, url_prefix=app_config['BASE_URL_PREFIX'])

# --- Thumbnail Generation Logic ---
# Supported image extensions
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp')

def is_image_file(filename):
    """Checks if a file has a supported image extension."""
    return filename.lower().endswith(IMAGE_EXTENSIONS)

def get_or_create_thumbnail(image_path: Path, thumbnail_path: Path, size: tuple):
    """
    Generates a thumbnail for an image if it doesn't already exist.
    """
    # Ensure the thumbnail directory exists
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)

    if thumbnail_path.exists():
        return # Thumbnail already exists

    print(f"Generating thumbnail for {image_path}...")
    try:
        with Image.open(image_path) as img:
            img.thumbnail(size) # Resize image proportionally
            img.save(thumbnail_path)
        print(f"Thumbnail saved to {thumbnail_path}")
    except Exception as e:
        print(f"Error generating thumbnail for {image_path}: {e}")

def scan_photos_and_generate_thumbnails():
    """
    Scans the PHOTOS_DIR for albums (subdirectories) and photos, including nested ones.
    Generates thumbnails for new images found.
    Populates a global dictionary with gallery data.
    """
    print("Starting photo scan and thumbnail generation...")
    gallery_data = {}

    photos_root = app_config['PHOTOS_DIR']
    thumbnails_root = app_config['THUMBNAILS_DIR']
    thumbnail_size = app_config['THUMBNAIL_SIZE']
    base_url_prefix = app_config['BASE_URL_PREFIX'] # Get the prefix

    thumbnails_root.mkdir(parents=True, exist_ok=True)

    # Use os.walk to traverse all subdirectories
    for dirpath, dirnames, filenames in os.walk(photos_root):
        # Calculate the relative path from the base photos directory.
        # This relative path will be our "album_name" which can include subdirectories.
        relative_path = Path(dirpath).relative_to(photos_root)
        album_name = str(relative_path).replace(os.sep, '/') # Use '/' for URLs

        # Filter for actual image files in the current directory
        current_dir_images = [f for f in filenames if is_image_file(f)]

        if current_dir_images: # Only consider directories that contain images as albums
            print(f"Processing album: {album_name if album_name != '.' else 'root'}")

            # Ensure the album entry exists in gallery_data, especially for root album
            if album_name not in gallery_data:
                gallery_data[album_name] = {
                    "cover_thumbnail_url": "",
                    "photos": []
                }

            album_photos = []
            album_thumbnail_dir = thumbnails_root / relative_path
            album_thumbnail_dir.mkdir(parents=True, exist_ok=True)

            # Sort images to ensure consistent ordering
            current_dir_images.sort(key=lambda x: x.lower())

            for photo_filename in current_dir_images:
                photo_path = Path(dirpath) / photo_filename
                thumbnail_path = album_thumbnail_dir / photo_filename

                get_or_create_thumbnail(photo_path, thumbnail_path, thumbnail_size)

                # Construct URLs for the frontend manually, now using the configurable base_url_prefix
                # Handle root album ('.') case to avoid double slashes
                original_url_segment = f"/photos/{album_name}/{photo_filename}" if album_name != '.' else f"/photos/{photo_filename}"
                thumb_url_segment = f"/thumbnails/{album_name}/{photo_filename}" if album_name != '.' else f"/thumbnails/{photo_filename}"

                original_url = base_url_prefix + original_url_segment
                thumb_url = base_url_prefix + thumb_url_segment

                album_photos.append({
                    "original_filename": photo_filename,
                    "original_url": original_url,
                    "thumbnail_url": thumb_url
                })

            gallery_data[album_name]["photos"].extend(album_photos)

            # Set album cover: first photo's thumbnail in the album
            if not gallery_data[album_name]["cover_thumbnail_url"] and album_photos:
                 gallery_data[album_name]["cover_thumbnail_url"] = album_photos[0]["thumbnail_url"]
            elif not gallery_data[album_name]["cover_thumbnail_url"]:
                # Use base_url_prefix for placeholder.png as well
                gallery_data[album_name]["cover_thumbnail_url"] = base_url_prefix + "/static/placeholder.png"

    # Clean up empty albums that might have been created but had no photos
    gallery_data = {k: v for k, v in gallery_data.items() if v["photos"]}

    print("Photo scan and thumbnail generation complete.")
    return gallery_data

# --- Flask Routes (now defined on the Blueprint) ---

# Store gallery data globally after initial scan
# This will be refreshed periodically or on demand in a real app,
# but for this lightweight example, we'll do it once at startup.
app.gallery_data = {}

# Call initial_scan directly during application startup.
with app.app_context():
    app.gallery_data = scan_photos_and_generate_thumbnails()


@gallery_bp.route('/')
def index():
    """Serves the main gallery page."""
    # Pass the base_url_prefix to the template
    return render_template('index.html', base_url_prefix=app_config['BASE_URL_PREFIX'])

@gallery_bp.route('/album/<path:album_name>')
def album_page(album_name):
    """Serves a specific album page."""
    # Pass the base_url_prefix to the template
    return render_template('album.html', album_name=album_name, base_url_prefix=app_config['BASE_URL_PREFIX'])

@gallery_bp.route('/api/albums')
def api_albums():
    """Returns a JSON list of all albums."""
    albums_list = []
    # Adjust how album names are handled for the root directory display
    for album_name, data in app.gallery_data.items():
        display_name = album_name if album_name != '.' else 'Root Gallery'
        albums_list.append({
            "name": album_name, # Actual album name (e.g., 'family/vacation')
            "display_name": display_name, # Name to show in UI
            "cover_thumbnail_url": data["cover_thumbnail_url"],
            "photo_count": len(data["photos"])
        })
    # Sort albums by display name
    albums_list.sort(key=lambda x: x['display_name'].lower())
    return jsonify(albums_list)

@gallery_bp.route('/api/album/<path:album_name>/photos')
def api_album_photos(album_name):
    """Returns a JSON list of photos for a specific album."""
    album_data = app.gallery_data.get(album_name)
    if album_data:
        return jsonify(album_data["photos"])
    return jsonify({"error": "Album not found"}), 404

@gallery_bp.route('/photos/<path:filename>')
def serve_photo(filename):
    """Serves original photo files. Filename now includes album subpaths."""
    # Split the filename into directory parts and the actual file name
    # The Path object handles cross-OS path separators internally
    full_photo_path_in_root = app_config['PHOTOS_DIR'] / filename

    if not full_photo_path_in_root.is_file():
        return "Photo not found", 404

    # send_from_directory needs the directory containing the file, and the file's base name
    # So we split the full path into its directory and the actual file name
    directory_to_serve_from = full_photo_path_in_root.parent
    file_base_name = full_photo_path_in_root.name

    return send_from_directory(directory_to_serve_from, file_base_name)

@gallery_bp.route('/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    """Serves generated thumbnail files. Filename now includes album subpaths."""
    # Similar to serve_photo, reconstruct the full path in the thumbnails directory
    full_thumbnail_path_in_root = app_config['THUMBNAILS_DIR'] / filename

    if not full_thumbnail_path_in_root.is_file():
        return "Thumbnail not found", 404

    directory_to_serve_from = full_thumbnail_path_in_root.parent
    file_base_name = full_thumbnail_path_in_root.name

    return send_from_directory(directory_to_serve_from, file_base_name)

# Register the blueprint with the main Flask application
# It's important to set a static_url_path if you want to serve static files
# for the main app under the base_url_prefix.
# If your static folder is not intended to be prefixed (e.g. /static/foo.png not /gallery/static/foo.png)
# then you would not set static_url_path here or use url_for('static', ...)
# However, given the problem, it suggests static files *should* be prefixed.
app.register_blueprint(gallery_bp, static_folder='static', static_url_path=app_config['BASE_URL_PREFIX'] + '/static')


# --- Main execution ---
if __name__ == '__main__':
    # Ensure the photos and thumbnails directories exist
    app_config['PHOTOS_DIR'].mkdir(parents=True, exist_ok=True)
    app_config['THUMBNAILS_DIR'].mkdir(parents=True, exist_ok=True)

    print(f"Starting Flask app on http://127.0.0.1:{app_config['PORT']}")
    app.run(host='0.0.0.0', port=app_config['PORT'], debug=True)

