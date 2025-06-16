# app.py
import os
import configparser
from flask import Flask, render_template, send_from_directory, jsonify, url_for
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

# Initialize Flask app after config is loaded
app = Flask(__name__)

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
    Scans the PHOTOS_DIR for albums (subdirectories) and photos.
    Generates thumbnails for new images found.
    Populates a global dictionary with gallery data.
    """
    print("Starting photo scan and thumbnail generation...")
    # This dictionary will store our gallery data:
    # {
    #   "album_name": {
    #       "cover_thumbnail_url": "...",
    #       "photos": [
    #           {"original_url": "...", "thumbnail_url": "..."},
    #           ...
    #       ]
    #   },
    #   ...
    # }
    gallery_data = {}

    photos_root = app_config['PHOTOS_DIR']
    thumbnails_root = app_config['THUMBNAILS_DIR']
    thumbnail_size = app_config['THUMBNAIL_SIZE']

    # Ensure the root thumbnail directory exists
    thumbnails_root.mkdir(parents=True, exist_ok=True)

    # Walk through the photos directory to find albums and images
    # We only care about immediate subdirectories as albums
    for album_dir in os.listdir(photos_root):
        album_path = photos_root / album_dir
        if album_path.is_dir():
            print(f"Processing album: {album_dir}")
            gallery_data[album_dir] = {
                "cover_thumbnail_url": "", # Will be set later
                "photos": []
            }
            album_photos = []
            album_thumbnail_dir = thumbnails_root / album_dir
            album_thumbnail_dir.mkdir(parents=True, exist_ok=True)

            # Find images within this album directory
            for photo_filename in os.listdir(album_path):
                photo_path = album_path / photo_filename
                if photo_path.is_file() and is_image_file(photo_filename):
                    thumbnail_filename = photo_filename # Keep same filename for thumbnail
                    thumbnail_path = album_thumbnail_dir / thumbnail_filename

                    get_or_create_thumbnail(photo_path, thumbnail_path, thumbnail_size)

                    # Construct URLs for the frontend
                    original_url = url_for('serve_photo', filename=f"{album_dir}/{photo_filename}")
                    thumb_url = url_for('serve_thumbnail', filename=f"{album_dir}/{thumbnail_filename}")

                    album_photos.append({
                        "original_filename": photo_filename,
                        "original_url": original_url,
                        "thumbnail_url": thumb_url
                    })

            # Sort photos by filename for consistent order
            album_photos.sort(key=lambda x: x['original_filename'].lower())
            gallery_data[album_dir]["photos"] = album_photos

            # Set album cover: first photo's thumbnail in the album
            if album_photos:
                gallery_data[album_dir]["cover_thumbnail_url"] = album_photos[0]["thumbnail_url"]
            else:
                # If no photos in album, use a placeholder or default
                gallery_data[album_dir]["cover_thumbnail_url"] = "/static/placeholder.png" # You could add a placeholder image

    print("Photo scan and thumbnail generation complete.")
    return gallery_data

# --- Flask Routes ---

# Store gallery data globally after initial scan
# This will be refreshed periodically or on demand in a real app,
# but for this lightweight example, we'll do it once at startup.
app.gallery_data = {}

# Call initial_scan directly during application startup,
# but within a test request context to allow url_for to function.
with app.app_context():
    with app.test_request_context():
        app.gallery_data = scan_photos_and_generate_thumbnails()


@app.route('/')
def index():
    """Serves the main gallery page."""
    return render_template('index.html')

@app.route('/album/<album_name>')
def album_page(album_name):
    """Serves a specific album page."""
    # This route is primarily for the client-side routing in JS to work
    return render_template('album.html', album_name=album_name)

@app.route('/api/albums')
def api_albums():
    """Returns a JSON list of all albums."""
    albums_list = []
    for album_name, data in app.gallery_data.items():
        albums_list.append({
            "name": album_name,
            "cover_thumbnail_url": data["cover_thumbnail_url"],
            "photo_count": len(data["photos"])
        })
    # Sort albums by name
    albums_list.sort(key=lambda x: x['name'].lower())
    return jsonify(albums_list)

@app.route('/api/album/<album_name>/photos')
def api_album_photos(album_name):
    """Returns a JSON list of photos for a specific album."""
    album_data = app.gallery_data.get(album_name)
    if album_data:
        return jsonify(album_data["photos"])
    return jsonify({"error": "Album not found"}), 404

@app.route('/photos/<path:filename>')
def serve_photo(filename):
    """Serves original photo files."""
    # Security note: Ensure filename cannot traverse directories (Flask's send_from_directory handles this well)
    # The filename path here will include the album folder, e.g., 'album1/photo1.jpg'
    album_name, photo_name = os.path.split(filename)
    full_path_to_album = app_config['PHOTOS_DIR'] / album_name
    if not full_path_to_album.exists():
        return "Album not found", 404
    return send_from_directory(full_path_to_album, photo_name)

@app.route('/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    """Serves generated thumbnail files."""
    # The filename path here will include the album folder, e.g., 'album1/photo1.jpg'
    album_name, thumb_name = os.path.split(filename)
    full_path_to_album_thumb = app_config['THUMBNAILS_DIR'] / album_name
    if not full_path_to_album_thumb.exists():
        return "Thumbnail album not found", 404
    return send_from_directory(full_path_to_album_thumb, thumb_name)

# --- Main execution ---
if __name__ == '__main__':
    # Ensure the photos and thumbnails directories exist
    app_config['PHOTOS_DIR'].mkdir(parents=True, exist_ok=True)
    app_config['THUMBNAILS_DIR'].mkdir(parents=True, exist_ok=True)

    # You can populate the `photos` directory with some test images like this:
    # Example: Create dummy photo files for testing
    # For a real application, users would place their photos here.
    # import shutil
    # dummy_photo_dir = Path("./dummy_photos")
    # dummy_photo_dir.mkdir(exist_ok=True)
    # if not (dummy_photo_dir / "test_album").exists():
    #     (dummy_photo_dir / "test_album").mkdir()
    #     # Create some placeholder images if they don't exist
    #     try:
    #         from PIL import Image, ImageDraw
    #         img1 = Image.new('RGB', (800, 600), color = 'red')
    #         d1 = ImageDraw.Draw(img1)
    #         d1.text((10,10), "Photo 1", fill=(255,255,0))
    #         img1.save(dummy_photo_dir / "test_album" / "photo1.jpg")
    #
    #         img2 = Image.new('RGB', (1024, 768), color = 'blue')
    #         d2 = ImageDraw.Draw(img2)
    #         d2.text((10,10), "Photo 2", fill=(255,0,255))
    #         img2.save(dummy_photo_dir / "test_album" / "photo2.png")
    #
    #         img3 = Image.new('RGB', (640, 480), color = 'green')
    #         d3 = ImageDraw.Draw(img3)
    #         d3.text((10,10), "Photo 3", fill=(0,255,255))
    #         img3.save(dummy_photo_dir / "test_album" / "photo3.jpeg")
    #
    #         print("Dummy photos created in ./dummy_photos/test_album")
    #     except ImportError:
    #         print("Pillow not installed. Cannot create dummy images.")
    #
    # if not app_config['PHOTOS_DIR'].exists() or not list(app_config['PHOTOS_DIR'].iterdir()):
    #     print(f"'{app_config['PHOTOS_DIR']}' is empty. You might want to copy dummy photos into it.")
    #     if dummy_photo_dir.exists() and list(dummy_photo_dir.iterdir()):
    #         print(f"Copying dummy photos from '{dummy_photo_dir}' to '{app_config['PHOTOS_DIR']}'...")
    #         # Simple copy - be careful in production
    #         for item in dummy_photo_dir.iterdir():
    #             if item.is_dir():
    #                 shutil.copytree(item, app_config['PHOTOS_DIR'] / item.name, dirs_exist_ok=True)
    #             elif item.is_file():
    #                 shutil.copy2(item, app_config['PHOTOS_DIR'] / item.name)


    print(f"Starting Flask app on http://127.0.0.1:{app_config['PORT']}")
    app.run(host='0.0.0.0', port=app_config['PORT'], debug=True)
