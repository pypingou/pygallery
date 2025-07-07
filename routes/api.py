# routes/api.py
"""API routes for JSON endpoints in pygallery."""

from flask import jsonify, request

from models.gallery import gallery


def register_api_routes(blueprint):
    """Register API routes with the given blueprint."""
    
    @blueprint.route('/api/albums')
    def api_albums():
        """
        Returns a JSON response indicating gallery mode (flat or nested) and album/photo data.
        """
        print(f"Request URL: {request.url}")
        print(f"Request script_root: {request.script_root}")
        
        albums_data = gallery.get_albums_data()
        return jsonify(albums_data)


    @blueprint.route('/api/album/<path:album_name>/photos')
    def api_album_photos_nested(album_name):
        """
        Returns photos for nested albums. This endpoint explicitly expects '/photos' suffix.
        """
        print(f"--- API photos requested for album: {album_name} (RUNTIME - Nested) ---")
        photos = gallery.get_album_photos(album_name)
        return jsonify(photos)


    @blueprint.route('/api/album/__root__')
    def api_album_photos_root():
        """
        Returns photos for the special '__root__' album.
        This endpoint handles requests without the '/photos' suffix for the root.
        """
        print(f"--- API photos requested for album: __root__ (RUNTIME - Root) ---")
        photos = gallery.get_album_photos('__root__')
        return jsonify(photos)

 