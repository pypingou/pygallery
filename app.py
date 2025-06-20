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
# Removed BASE_URL_PREFIX from app_config, as the app is agnostic to it.
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
        app_config['PHOTOS_DIR'] = config['Gallery'].get('PHOTOS_DIR', './photos')
        app_config['THUMBNAILS_DIR'] = config['Gallery'].get('THUMBNAILS_DIR', './thumbnails')
        app_config['THUMBNAIL_SIZE'] = tuple(map(int, config['Gallery'].get('THUMBNAIL_SIZE', '200,200').split(',')))
        app_config['PORT'] = int(config['Gallery'].get('PORT', '5000'))
    except ValueError as e:
        print(f"Error parsing configuration: {e}")
        exit(1)

    # Ensure paths are absolute for safety, or relative to the app's root
    app_config['PHOTOS_DIR'] = Path(app_config['PHOTOS_DIR']).resolve()
    app_config['THUMBNAILS_DIR'] = Path(app_config['THUMBNAILS_DIR']).resolve()

    print(f"Configuration loaded: {app_config}")

# Load configuration when the script starts
load_config()

# Initialize Flask app - it will internally run at root '/'
# Static files are handled by the blueprint's static_folder/static_url_path.
app = Flask(__name__)

# --- Apply ProxyFix to the Flask application ---
# This middleware is crucial. It corrects Flask's understanding of the request environment
# based on X-Forwarded-* headers (like X-Forwarded-Proto, X-Forwarded-Prefix).
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_prefix=1, x_proto=1)

# --- Create a Blueprint for the gallery ---
# The blueprint's URL prefix is now its internal path relative to app root.
# We define the static folder and its URL path here, relative to the blueprint.
gallery_bp = Blueprint('gallery', __name__,
                       template_folder='templates',
                       static_folder='static', # Refers to the 'static' directory relative to app.py
                       static_url_path='/static') # This makes the blueprint's static files available at /static relative to its own root

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
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    if thumbnail_path.exists():
        return
    print(f"Generating thumbnail for {image_path}...")
    try:
        with Image.open(image_path) as img:
            img.thumbnail(size)
            img.save(thumbnail_path)
        print(f"Thumbnail saved to {thumbnail_path}")
    except Exception as e:
        print(f"Error generating thumbnail for {image_path}: {e}")

# IMPORTANT: base_url_prefix is NOT used directly for URL construction in this function anymore.
# We rely on url_for within a test_request_context for correct URL generation.
def scan_photos_and_generate_thumbnails():
    """
    Scans the PHOTOS_DIR for albums and photos.
    Generates thumbnails and populates gallery data with URLs.
    URLs are generated using url_for within a test context simulating proxy.
    """
    print("Starting photo scan and thumbnail generation...")
    gallery_data = {}

    photos_root = app_config['PHOTOS_DIR']
    thumbnails_root = app_config['THUMBNAILS_DIR']
    thumbnail_size = app_config['THUMBNAIL_SIZE']
    
    thumbnails_root.mkdir(parents=True, exist_ok=True)

    # Re-introducing test_request_context around the scan_photos_and_generate_thumbnails logic
    # within the app.py's main execution block. This ensures url_for works at startup.
    # The parameters for base_url and url_scheme are set to simulate the deployed environment
    # where Flask runs internally at '/' and Apache handles external prefix/HTTPS.
    # SCRIPT_NAME will be effectively '/' for url_for in this context.
    # NEW: Use external_scheme, external_server, external_prefix for base_url and url_for
    external_scheme = os.environ.get('wsgi.url_scheme', 'http') # 'https' when proxied by Apache
    external_server = os.environ.get('SERVER_NAME', 'localhost') # 'example.com' when proxied by Apache
    external_port = os.environ.get('SERVER_PORT', str(app_config['PORT'])) # '443' when proxied by Apache
    # SCRIPT_NAME is '/' internally, but for url_for to generate *external* URLs,
    # ProxyFix uses X-Forwarded-Prefix. So, we simulate the external prefix for url_for to work.
    # This prefix comes from X-Forwarded-Prefix set by Apache, or from ENVIRONMENT in test context.
    external_script_name = os.environ.get('SCRIPT_NAME', '/') # This is the app's *internal* root.
                                                              # For url_for to generate external URLs,
                                                              # it needs to be aware of the external prefix.
                                                              # This is why we use _external=True and
                                                              # ensure the test_request_context's base_url is full external.


    with app.test_request_context(
        path=external_script_name, # Internal path Flask sees (e.g., '/')
        base_url=f"{external_scheme}://{external_server}:{external_port}" # Full external base URL
        # Removed url_scheme=external_scheme here to avoid AssertionError
    ):
        # Ensure SCRIPT_NAME is set in the test context
        request.environ['SCRIPT_NAME'] = external_script_name
        request.environ['SERVER_NAME'] = external_server
        request.environ['SERVER_PORT'] = external_port
        request.environ['wsgi.url_scheme'] = external_scheme


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

                    # NEW: Use _external=True with url_for to generate absolute URLs
                    # ProxyFix and the context will ensure the correct domain/scheme/prefix.
                    original_url = url_for('gallery.serve_photo', filename=f"{album_name}/{photo_filename}" if album_name != '.' else photo_filename, _external=True)
                    thumb_url = url_for('gallery.serve_thumbnail', filename=f"{album_name}/{photo_filename}" if album_name != '.' else photo_filename, _external=True)

                    album_photos.append({
                        "original_filename": photo_filename,
                        "original_url": original_url,
                        "thumbnail_url": thumb_url
                    })

                gallery_data[album_name]["photos"].extend(album_photos)

                if not gallery_data[album_name]["cover_thumbnail_url"] and album_photos:
                     gallery_data[album_name]["cover_thumbnail_url"] = album_photos[0]["thumbnail_url"]
                elif not gallery_data[album_name]["cover_thumbnail_url"]:
                    # Use _external=True for placeholder as well
                    gallery_data[album_name]["cover_thumbnail_url"] = url_for('gallery.static', filename='placeholder.png', _external=True)

    # Clean up empty albums that might have been created but had no photos
    gallery_data = {k: v for k, v in gallery_data.items() if v["photos"]}

    print("Photo scan and thumbnail generation complete.")
    return gallery_data

# --- Flask Routes (now defined on the Blueprint) ---

# Store gallery data globally after initial scan
app.gallery_data = {}

# Call initial_scan is now done within the context of os.environ setup in __main__
# It is important that this call happens after environment variables for url_for are set.


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
# The url_prefix for the blueprint is NOT explicitly set here.
# It will be derived by Flask at runtime from the SCRIPT_NAME environment variable
# (which Gunicorn/Apache set) combined with ProxyFix.
# The blueprint's routes will internally act as if they are at the app's internal root.
app.register_blueprint(gallery_bp)


# --- Main execution ---
if __name__ == '__main__':
    # For local development, simulate the SCRIPT_NAME and SERVER_NAME
    # that Gunicorn/Apache would provide in a deployed environment.
    # This allows url_for to generate correct URLs during initial scan.
    # The SCRIPT_NAME will determine the effective "APPLICATION_ROOT" for url_for.
    # The SERVER_NAME will determine the hostname.
    # For local testing, SCRIPT_NAME should be '/' as the app runs internally at root.
    # Ensure all required environment variables are set before trying to access them
    # and before calling scan_photos_and_generate_thumbnails.
    os.environ['SCRIPT_NAME'] = os.environ.get('SCRIPT_NAME', '/') # Internal root
    os.environ['SERVER_NAME'] = os.environ.get('SERVER_NAME', 'localhost')
    os.environ['SERVER_PORT'] = os.environ.get('SERVER_PORT', str(app_config['PORT']))
    os.environ['wsgi.url_scheme'] = os.environ.get('wsgi.url_scheme', 'http') # Default to http for local

    # Call scan_photos_and_generate_thumbnails directly at startup, wrapped in test_request_context
    # This will ensure url_for generates correct URLs (internal to the Flask app).
    with app.test_request_context(
        path=os.environ['SCRIPT_NAME'], # Path is the app's root, e.g., '/'
        base_url=f"{os.environ['wsgi.url_scheme']}://{os.environ['SERVER_NAME']}:{os.environ['SERVER_PORT']}"
    ):
        request.environ['SCRIPT_NAME'] = os.environ['SCRIPT_NAME'] # Ensure SCRIPT_NAME is set in test context
        app.gallery_data = scan_photos_and_generate_thumbnails() # Call function without base_url_prefix argument


    print(f"Starting Flask app on {os.environ.get('wsgi.url_scheme', 'http')}://{os.environ.get('SERVER_NAME', 'localhost')}:{os.environ.get('SERVER_PORT', '5000')}{os.environ.get('SCRIPT_NAME', '/')}")
    app.run(host='0.0.0.0', port=app_config['PORT'], debug=True)

