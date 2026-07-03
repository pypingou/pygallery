# app.py
"""Main application entry point for pygallery."""

import os
import logging
from typing import Callable
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

# Import modules
from config.settings import config
from routes.views import gallery_bp
from utils.image_processing import scan_and_generate_all_thumbnails


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('pygallery.log'),
            logging.StreamHandler()
        ]
    )
    
    # Apply ProxyFix to the Flask application
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_prefix=1, x_proto=1)
    
    # Register blueprints
    app.register_blueprint(gallery_bp)
    
    return app


# Create Flask app instance for gunicorn
app = create_app()

# Ensure directories exist
photos_dir = config.get('PHOTOS_DIR')
thumbnails_dir = config.get('THUMBNAILS_DIR')
photos_dir.mkdir(parents=True, exist_ok=True)
thumbnails_dir.mkdir(parents=True, exist_ok=True)

# Generate thumbnails at startup (runs once when gunicorn loads the module)
with app.test_request_context():
    scan_and_generate_all_thumbnails()


def main() -> None:
    """Main application entry point for local development."""
    port = config.get('PORT')

    # For local development, simulate the SCRIPT_NAME and SERVER_NAME
    # that Gunicorn/Apache would provide in a deployed environment.
    os.environ['SCRIPT_NAME'] = os.environ.get('SCRIPT_NAME', '/')  # Internal root
    os.environ['SERVER_NAME'] = os.environ.get('SERVER_NAME', 'localhost')
    os.environ['SERVER_PORT'] = os.environ.get('SERVER_PORT', str(port))
    os.environ['wsgi.url_scheme'] = os.environ.get('wsgi.url_scheme', 'http')  # Default to http for local

    print(f"Starting Flask app on {os.environ.get('wsgi.url_scheme', 'http')}://{os.environ.get('SERVER_NAME', 'localhost')}:{os.environ.get('SERVER_PORT', '5000')}{os.environ.get('SCRIPT_NAME', '/')}")

    # Check if we're in a problematic environment (like Cursor) that breaks Flask's reloader
    debug_mode = True
    use_reloader = True

    # Disable reloader if we detect issues with the environment
    if 'Cursor' in os.environ.get('_', '') or 'AppImage' in str(os.environ.get('_', '')):
        use_reloader = False
        logging.warning("Detected problematic environment, disabling Flask reloader")

    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=use_reloader)


if __name__ == '__main__':
    main()

