# routes/views.py
"""View routes for rendering templates in pygallery."""

from flask import Blueprint, render_template, send_from_directory, abort, Response
from pathlib import Path
from typing import Union
import logging

from config.settings import config
from utils.security import validate_album_name, validate_filename, safe_path_join, SecurityError, sanitize_error_message


# Create a Blueprint for the gallery
gallery_bp = Blueprint('gallery', __name__,
                       template_folder='templates',
                       static_folder='static',
                       static_url_path='/static')


# Register API routes on this blueprint
from routes.api import register_api_routes
register_api_routes(gallery_bp)


@gallery_bp.route('/')
def index() -> str:
    """Serves the main gallery page."""
    return render_template('index.html')


@gallery_bp.route('/album/<path:album_name>')
def album_page(album_name: str) -> str:
    """Serves a specific album page."""
    try:
        # Validate and sanitize album name
        sanitized_album_name = validate_album_name(album_name)
        return render_template('album.html', album_name=sanitized_album_name)
    except SecurityError as e:
        logging.warning(f"Security error in album_page: {e}")
        abort(400, description="Invalid album name")
    except Exception as e:
        logging.error(f"Error in album_page: {e}")
        abort(500, description="Internal server error")


@gallery_bp.route('/photos/<path:filename>')
def serve_photo(filename: str) -> Response:
    """Serves original photo files. Filename now includes album subpaths."""
    try:
        # Validate filename components
        photos_dir = config.get('PHOTOS_DIR')
        
        # Use safe path join to prevent directory traversal
        full_photo_path = safe_path_join(photos_dir, filename)
        
        if not full_photo_path.is_file():
            logging.warning(f"Photo not found: {sanitize_error_message(str(full_photo_path))}")
            abort(404, description="Photo not found")

        directory_to_serve_from = full_photo_path.parent
        file_base_name = full_photo_path.name
        logging.info(f"Serving photo: {sanitize_error_message(str(full_photo_path))}")
        return send_from_directory(directory_to_serve_from, file_base_name)
        
    except SecurityError as e:
        logging.warning(f"Security error in serve_photo: {e}")
        abort(400, description="Invalid filename")
    except Exception as e:
        logging.error(f"Error in serve_photo: {e}")
        abort(500, description="Internal server error")


@gallery_bp.route('/thumbnails/<path:filename>')
def serve_thumbnail(filename: str) -> Response:
    """Serves generated thumbnail files. Filename now includes album subpaths."""
    try:
        # Validate filename components
        thumbnails_dir = config.get('THUMBNAILS_DIR')
        
        # Use safe path join to prevent directory traversal
        full_thumbnail_path = safe_path_join(thumbnails_dir, filename)
        
        if not full_thumbnail_path.is_file():
            logging.warning(f"Thumbnail not found: {sanitize_error_message(str(full_thumbnail_path))}")
            abort(404, description="Thumbnail not found")

        directory_to_serve_from = full_thumbnail_path.parent
        file_base_name = full_thumbnail_path.name
        logging.info(f"Serving thumbnail: {sanitize_error_message(str(full_thumbnail_path))}")
        return send_from_directory(directory_to_serve_from, file_base_name)
        
    except SecurityError as e:
        logging.warning(f"Security error in serve_thumbnail: {e}")
        abort(400, description="Invalid filename")
    except Exception as e:
        logging.error(f"Error in serve_thumbnail: {e}")
        abort(500, description="Internal server error") 