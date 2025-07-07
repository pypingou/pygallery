# routes/api.py
"""API routes for JSON endpoints in pygallery."""

from flask import jsonify, request, abort, Response
from typing import Union, Tuple
import logging

from models.gallery import gallery
from utils.security import validate_album_name, SecurityError, sanitize_error_message
from utils.rate_limiter import rate_limit


def register_api_routes(blueprint: 'Blueprint') -> None:
    """Register API routes with the given blueprint."""
    
    @blueprint.route('/api/albums')
    @rate_limit('api.api_albums')
    def api_albums() -> Union[Response, Tuple[Response, int]]:
        """
        Returns a JSON response indicating gallery mode (flat or nested) and album/photo data.
        """
        try:
            logging.info(f"API albums request from {request.remote_addr}")
            albums_data = gallery.get_albums_data()
            return jsonify(albums_data)
        except Exception as e:
            logging.error(f"Error in api_albums: {e}")
            return jsonify({
                'error': 'Internal server error',
                'message': 'Unable to retrieve albums data'
            }), 500


    @blueprint.route('/api/album/<path:album_name>/photos')
    @rate_limit('api.api_album_photos_nested')
    def api_album_photos_nested(album_name: str) -> Union[Response, Tuple[Response, int]]:
        """
        Returns photos for nested albums. This endpoint explicitly expects '/photos' suffix.
        """
        try:
            # Validate and sanitize album name
            sanitized_album_name = validate_album_name(album_name)
            logging.info(f"API photos requested for album: {sanitize_error_message(sanitized_album_name)}")
            
            photos = gallery.get_album_photos(sanitized_album_name)
            return jsonify(photos)
        except SecurityError as e:
            logging.warning(f"Security error in api_album_photos_nested: {e}")
            return jsonify({
                'error': 'Invalid album name',
                'message': 'The provided album name is invalid'
            }), 400
        except Exception as e:
            logging.error(f"Error in api_album_photos_nested: {e}")
            return jsonify({
                'error': 'Internal server error',
                'message': 'Unable to retrieve photos for this album'
            }), 500


    @blueprint.route('/api/album/__root__')
    @rate_limit('api.api_album_photos_root')
    def api_album_photos_root() -> Union[Response, Tuple[Response, int]]:
        """
        Returns photos for the special '__root__' album.
        This endpoint handles requests without the '/photos' suffix for the root.
        """
        try:
            logging.info("API photos requested for root album")
            photos = gallery.get_album_photos('__root__')
            return jsonify(photos)
        except Exception as e:
            logging.error(f"Error in api_album_photos_root: {e}")
            return jsonify({
                'error': 'Internal server error',
                'message': 'Unable to retrieve photos for root album'
            }), 500

 