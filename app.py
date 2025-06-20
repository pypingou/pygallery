# app.py
import os
import configparser
from flask import Flask, render_template, send_from_directory, jsonify, Blueprint, url_for, Request
from PIL import Image
from pathlib import Path
import threading
import time
from werkzeug.middleware.proxy_fix import ProxyFix # Import ProxyFix

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

# Initialize Flask app
# Static files are handled by the default Flask static folder/route
app = Flask(__name__)

# --- NEW: Set APPLICATION_ROOT for Flask's internal URL generation ---
# This is crucial for Flask to correctly build URLs when deployed at a subpath.
app.config['APPLICATION_ROOT'] = app_config['BASE_URL_PREFIX'] if app_config['BASE_URL_PREFIX'] else '/'

# --- Apply ProxyFix to the Flask application ---
# This middleware corrects Flask's understanding of the request environment
# when running behind a reverse proxy (like Apache/Nginx).
# x_for: X-Forwarded-For (client IP)
# x_host: X-Forwarded-Host (original host header)
# x_proto: X-Forwarded-Proto (original protocol, http/https)
# x_prefix: X-Forwarded-Prefix (original URL prefix, sets SCRIPT_NAME)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_prefix=1, x_proto=1)


# --- Create a Blueprint for the gallery with a configurable URL prefix ---
# static_folder and static_url_path are NOT set on the Blueprint.
# Flask's main app static handler will serve files based on its static_url_path (default is /static, relative to APPLICATION_ROOT)
gallery_bp = Blueprint('gallery', __name__,
                       url_prefix=app_config['BASE_URL_PREFIX'],
                       template_folder='templates') # Explicitly set template folder for blueprint

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

    thumbnails_root.mkdir(parents=True, exist_ok=True)

    # NEW: Create a dummy request context to allow url_for to work during scan
    with app.test_request_context('/'):
        # Set the SCRIPT_NAME within this context for correct url_for generation
        # This simulates the reverse proxy setting SCRIPT_NAME
        app.wsgi_app.default_environ['SCRIPT_NAME'] = app_config['BASE_URL_PREFIX']
        app.wsgi_app.default_environ['SERVER_NAME'] = 'localhost' # Dummy server name
        app.wsgi_app.default_environ['SERVER_PORT'] = '5000'
        app.wsgi_app.default_environ['wsgi.url_scheme'] = 'http' # Assume http internally

        for dirpath, dirnames, filenames in os.walk(photos_root):
            relative_path = Path(dirpath).relative_to(photos_root)
            album_name = str(relative_path).replace(os.sep, '/')

            current_dir_images = [f for f in filenames if is_image_file(f)]

            if current_dir_images:
                print(f"Processing album: {album_name if album_name != '.' else 'root'}")

                if album_name not in gallery_data:
                    gallery_data[album_name] = {
                        "cover_thumbnail_url": "",
                        "photos": []
                    }

                album_photos = []
                album_thumbnail_dir = thumbnails_root / relative_path
                album_thumbnail_dir.mkdir(parents=True, exist_ok=True)

                current_dir_images.sort(key=lambda x: x.lower())

                for photo_filename in current_dir_images:
                    photo_path = Path(dirpath) / photo_filename
                    thumbnail_path = album_thumbnail_dir / photo_filename

                    get_or_create_thumbnail(photo_path, thumbnail_path, thumbnail_size)

                    # NEW: Use url_for for robustness
                    # For photos and thumbnails, we need to manually create the full path
                    # and then pass it as a 'filename' argument to the respective endpoint.
                    # Flask's static endpoint will work with its default /static mapping.
                    original_url = url_for('gallery.serve_photo', filename=f"{album_name}/{photo_filename}" if album_name != '.' else photo_filename)
                    thumb_url = url_for('gallery.serve_thumbnail', filename=f"{album_name}/{photo_filename}" if album_name != '.' else photo_filename)


                    album_photos.append({
                        "original_filename": photo_filename,
                        "original_url": original_url,
                        "thumbnail_url": thumb_url
                    })

                gallery_data[album_name]["photos"].extend(album_photos)

                if not gallery_data[album_name]["cover_thumbnail_url"] and album_photos:
                     gallery_data[album_name]["cover_thumbnail_url"] = album_photos[0]["thumbnail_url"]
                elif not gallery_data[album_name]["cover_thumbnail_url"]:
                    # NEW: Use url_for for placeholder image
                    gallery_data[album_name]["cover_thumbnail_url"] = url_for('static', filename='placeholder.png')

    # Clean up empty albums that might have been created but had no photos
    gallery_data = {k: v for k, v in gallery_data.items() if v["photos"]}

    print("Photo scan and thumbnail generation complete.")
    return gallery_data

# --- Flask Routes (now defined on the Blueprint) ---

# Store gallery data globally after initial scan
app.gallery_data = {}

# Call initial_scan directly during application startup.
with app.app_context():
    app.gallery_data = scan_photos_and_generate_thumbnails()


@gallery_bp.route('/')
def index():
    """Serves the main gallery page."""
    # base_url_prefix is no longer needed in render_template if url_for is used
    return render_template('index.html')

@gallery_bp.route('/album/<path:album_name>')
def album_page(album_name):
    """Serves a specific album page."""
    # base_url_prefix is no longer needed in render_template if url_for is used
    return render_template('album.html', album_name=album_name)

@gallery_bp.route('/api/albums')
def api_albums():
    """Returns a JSON list of all albums."""
    albums_list = []
    for album_name, data in app.gallery_data.items():
        display_name = album_name if album_name != '.' else 'Root Gallery'
        albums_list.append({
            "name": album_name,
            "display_name": display_name,
            "cover_thumbnail_url": data["cover_thumbnail_url"],
            "photo_count": len(data["photos"])
        })
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
    full_photo_path_in_root = app_config['PHOTOS_DIR'] / filename

    if not full_photo_path_in_root.is_file():
        return "Photo not found", 404

    directory_to_serve_from = full_photo_path_in_root.parent
    file_base_name = full_photo_path_in_root.name

    return send_from_directory(directory_to_serve_from, file_base_name)

@gallery_bp.route('/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    """Serves generated thumbnail files. Filename now includes album subpaths."""
    full_thumbnail_path_in_root = app_config['THUMBNAILS_DIR'] / filename

    if not full_thumbnail_path_in_root.is_file():
        return "Thumbnail not found", 404

    directory_to_serve_from = full_thumbnail_path_in_root.parent
    file_base_name = full_thumbnail_path_in_root.name

    return send_from_directory(directory_to_serve_from, file_base_name)

# Register the blueprint with the main Flask application.
app.register_blueprint(gallery_bp)

# --- Main execution ---
if __name__ == '__main__':
    # Ensure the photos and thumbnails directories exist
    app_config['PHOTOS_DIR'].mkdir(parents=True, exist_ok=True)
    app_config['THUMBNAILS_DIR'].mkdir(parents=True, exist_ok=True)

    print(f"Starting Flask app on http://127.0.0.1:{app_config['PORT']}")
    app.run(host='0.0.0.0', port=app_config['PORT'], debug=True)

