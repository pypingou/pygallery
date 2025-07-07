# routes/views.py
"""View routes for rendering templates in pygallery."""

from flask import Blueprint, render_template, send_from_directory
from pathlib import Path

from config.settings import config


# Create a Blueprint for the gallery
gallery_bp = Blueprint('gallery', __name__,
                       template_folder='templates',
                       static_folder='static',
                       static_url_path='/static')


# Register API routes on this blueprint
from routes.api import register_api_routes
register_api_routes(gallery_bp)


@gallery_bp.route('/')
def index():
    """Serves the main gallery page."""
    return render_template('index.html')


@gallery_bp.route('/album/<path:album_name>')
def album_page(album_name):
    """Serves a specific album page."""
    return render_template('album.html', album_name=album_name)


@gallery_bp.route('/photos/<path:filename>')
def serve_photo(filename):
    """Serves original photo files. Filename now includes album subpaths."""
    # This route expects filename to be the full path relative to PHOTOS_DIR
    # e.g., 'image.jpg' or 'USA/2010/10/image.jpg'
    photos_dir = config.get('PHOTOS_DIR')
    full_photo_path_in_root = photos_dir / filename

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
    # This route expects filename to be the full path relative to THUMBNAILS_DIR
    thumbnails_dir = config.get('THUMBNAILS_DIR')
    full_thumbnail_path_in_root = thumbnails_dir / filename

    if not full_thumbnail_path_in_root.is_file():
        print(f"Serve thumbnail: File not found - {full_thumbnail_path_in_root}")
        return "Thumbnail not found", 404

    directory_to_serve_from = full_thumbnail_path_in_root.parent
    file_base_name = full_thumbnail_path_in_root.name
    print(f"Serving thumbnail: {full_thumbnail_path_in_root}")
    return send_from_directory(directory_to_serve_from, file_base_name) 