# app.py
"""Main application entry point for pygallery."""

import os
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

# Import modules
from config.settings import config
from routes.views import gallery_bp
from utils.image_processing import scan_and_generate_all_thumbnails


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Apply ProxyFix to the Flask application
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_prefix=1, x_proto=1)
    
    # Register blueprints
    app.register_blueprint(gallery_bp)
    
    return app


def main():
    """Main application entry point."""
    # Create Flask app
    app = create_app()
    
    # Ensure root photo and thumbnail directories exist
    photos_dir = config.get('PHOTOS_DIR')
    thumbnails_dir = config.get('THUMBNAILS_DIR')
    port = config.get('PORT')
    
    photos_dir.mkdir(parents=True, exist_ok=True)
    thumbnails_dir.mkdir(parents=True, exist_ok=True)

    # For local development, simulate the SCRIPT_NAME and SERVER_NAME
    # that Gunicorn/Apache would provide in a deployed environment.
    # This allows url_for to generate correct URLs.
    os.environ['SCRIPT_NAME'] = os.environ.get('SCRIPT_NAME', '/')  # Internal root
    os.environ['SERVER_NAME'] = os.environ.get('SERVER_NAME', 'localhost')
    os.environ['SERVER_PORT'] = os.environ.get('SERVER_PORT', str(port))
    os.environ['wsgi.url_scheme'] = os.environ.get('wsgi.url_scheme', 'http')  # Default to http for local

    # Call the initial thumbnail generation scan at startup
    # This runs within a dummy request context so url_for works for local scan_and_generate_all_thumbnails calls.
    with app.test_request_context(
        path=os.environ['SCRIPT_NAME'],  # Path is the app's root, e.g., '/'
        base_url=f"{os.environ['wsgi.url_scheme']}://{os.environ['SERVER_NAME']}:{os.environ['SERVER_PORT']}"
    ):
        from flask import request
        request.environ['SCRIPT_NAME'] = os.environ['SCRIPT_NAME']  # Ensure SCRIPT_NAME is set
        scan_and_generate_all_thumbnails()  # This function now just generates thumbnails

    print(f"Starting Flask app on {os.environ.get('wsgi.url_scheme', 'http')}://{os.environ.get('SERVER_NAME', 'localhost')}:{os.environ.get('SERVER_PORT', '5000')}{os.environ.get('SCRIPT_NAME', '/')}")
    app.run(host='0.0.0.0', port=port, debug=True)


if __name__ == '__main__':
    main()

