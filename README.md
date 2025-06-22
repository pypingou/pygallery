# pygallery: My Lightweight Photo Gallery

This is a lightweight web application designed to serve as a simple photo gallery. It's built with Python (Flask) for the backend and uses HTML, CSS, and JavaScript for the frontend. The application allows you to browse photos organized in folders, view thumbnails, and see enlarged versions of images with navigation and download options. It's designed to be easily deployable using containers on a Fedora server.

---

## Features

* **Folder-based Albums:** Each folder on your disk corresponds to an album in the gallery.

* **Automatic Thumbnail Generation:** Thumbnails are automatically generated for photos if they don't already exist.

* **Responsive Web Interface:** Albums and photos are displayed in a responsive grid layout.

* **Lightbox View:** Click on a photo to see a larger version in a pop-up lightbox.

* **Image Navigation:** Use mouse clicks (on navigation arrows) or keyboard arrow keys (left/right) to browse photos within the lightbox.

* **Image Download:** A button within the lightbox allows easy downloading of the current image.

* **Containerized Deployment:** Ready for deployment as a container image using Podman/Docker, managed with Systemd/Quadlet on Fedora.

* **Configurable Display Mode:** Choose between a traditional album list view or a "flat" display where root-level photos are shown directly on the index page if no subfolders exist.

---

## Project Structure

```
pygallery/
├── app.py                      # Flask backend application
├── config.ini                  # Configuration file for the gallery
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Dockerfile to build the container image
├── pygallery-app.container     # Quadlet file for Systemd service (Fedora)
├── generate_dummy_images.py    # Script to create test images
├── static/
│   ├── css/
│   │   └── style.css           # Stylesheets for the web interface
│   └── js/
│       └── script.js           # JavaScript for dynamic behavior and lightbox
└── templates/
    ├── index.html              # Main gallery page (albums view)
    └── album.html              # Album detail page (photos view)
└── photos/                     # Directory for your original photo albums (mounted volume)
    └── AlbumName1/
        └── photo1.jpg
        └── photo2.png
    └── AlbumName2/
        └── photoA.jpeg
└── thumbnails/                 # Directory for generated thumbnails (mounted volume)
    └── AlbumName1/
        └── photo1.jpg
    └── AlbumName2/
        └── photoA.jpeg
```

---

## Setup and Installation

### Prerequisites

* Python 3.x

* `pip` (Python package installer)

* Podman or Docker (for containerized deployment)

* A Fedora server (for Quadlet deployment)

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd pygallery
```

### 2. Install Python Dependencies

It's recommended to use a virtual environment.

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

The `requirements.txt` file contains:

```
Flask
Pillow
gunicorn
```

### 3. Configure the Gallery

Create a `config.ini` file in the root of your project:

```ini
[Gallery]
PHOTOS_DIR = ./photos
THUMBNAILS_DIR = ./thumbnails
THUMBNAIL_SIZE = 200,200
PORT = 5000
```

* `PHOTOS_DIR`: Path to your original photo albums.

* `THUMBNAILS_DIR`: Path where generated thumbnails will be stored.

* `THUMBNAIL_SIZE`: Desired dimensions for thumbnails (width,height).

* `PORT`: The port Flask will listen on.

## Generating Dummy Images (Optional)

For testing purposes, you can use the provided script to generate some placeholder images:

```bash
python generate_dummy_images.py

```

This will create `photos/VacationPhotos` and `photos/Cityscapes` with sample images.

## Running the Application

### 1. Local Development (Python)

To run the Flask application directly (for development):

```
python app.py

```

Access the gallery at `http://127.0.0.1:5000/` (if `SCRIPT_NAME` is `/` in your local environment, or it will be `http://127.0.0.1:5000/gallery/` if you set `SCRIPT_NAME=/gallery` in your shell environment before running).

### 2. Containerized Deployment (Podman/Docker)

**Build the Image:**

```
# Using Podman
podman build -t pygallery .

# Using Docker
docker build -t pygallery .

```

**Run the Container (for testing, or if not using Quadlet/Apache):**

```
# Replace /path/to/your/actual/photos and /path/to/your/actual/thumbnails
# with your actual host directories.
HOST_PHOTOS_DIR="/home/user/my_gallery_photos"
HOST_THUMBNAILS_DIR="/home/user/my_gallery_thumbnails"

# IMPORTANT: Adjust SCRIPT_NAME to match your desired external path.
# For example, for http://your_server_ip:8000/gallery/
SCRIPT_NAME_VALUE="/gallery"

# Using Podman
podman run -d \
  --name pygallery-app \
  -p 8000:5000 \
  -v "${HOST_PHOTOS_DIR}":/app/photos:Z \
  -v "${HOST_THUMBNAILS_DIR}":/app/thumbnails:Z \
  --env SCRIPT_NAME="${SCRIPT_NAME_VALUE}" \
  pygallery

# Using Docker
docker run -d \
  --name pygallery-app \
  -p 8000:5000 \
  -v "${HOST_PHOTOS_DIR}":/app/photos \
  -v "${HOST_THUMBNAILS_DIR}":/app/thumbnails \
  --env SCRIPT_NAME="${SCRIPT_NAME_VALUE}" \
  pygallery

```

Access the gallery at `http://your_server_ip:8000/<YOUR_SCRIPT_NAME_VALUE>/`.

### 3. Deployment with Quadlet (Systemd Service on Fedora)

Quadlet allows you to manage your container as a systemd service.

**1. Place the Quadlet File:**

Save the `photo-gallery.container` file to `/etc/containers/systemd/`:

```
# /etc/containers/systemd/photo-gallery.container
[Container]
ContainerName=pygallery-app
Image=localhost/pygallery:latest
Volume=/home/user/my_gallery_photos:/app/photos:Z # **UPDATE THIS PATH**
Volume=/home/user/my_gallery_thumbnails:/app/thumbnails:Z # **UPDATE THIS PATH**
PublishPort=8000:5000 # Container port 5000 mapped to host port 8000
Network=my_gallery_network # Replace with your network name

# Set environment variables for the container.
# SCRIPT_NAME: This tells Gunicorn (and thus Flask via ProxyFix) its application mount point.
# This should match the path your Apache proxy routes to the container.
# IMPORTANT: Replace <YOUR_BASE_URL_PREFIX_VALUE> (e.g., /gallery, /myphotos)
Environment=SCRIPT_NAME=/ # Set to your desired subpath, or / for root.
Environment=GALLERY_MODE=ALBUM_DISPLAY # Set to 'FLAT_ROOT_DISPLAY' for direct root display mode.

[Unit]
Description=pygallery: My Lightweight Photo Gallery Container
Wants=network-online.target
After=network-online.target

[Service]
Restart=on-failure

```

**Remember to:**

* Replace the `Volume` paths with your actual host directories.

* Set `Environment=SCRIPT_NAME=/` to your desired subpath (e.g., `/gallery`) if deploying there, or `/` for root deployment.

* Set `Environment=GALLERY_MODE=FLAT_ROOT_DISPLAY` if you want the root page to show photos directly when no subfolders exist.

**2. Reload Systemd and Start Service:**

```
sudo systemctl daemon-reload
sudo systemctl start photo-gallery.service
sudo systemctl enable photo-gallery.service # To start on boot

```

Access the gallery at `http://your_server_ip:8000/<YOUR_SCRIPT_NAME_VALUE>/`.

### 4. Deploying with Apache Reverse Proxy at `/gallery` (HTTPS)

If Apache is already running on port 80/443, you can use it as a reverse proxy.

**1. Ensure Container is Running (Internal Port Only):**

Your Quadlet file (above) should have `PublishPort=8000:5000` or no `PublishPort` if only accessed via Apache.

**2. Apache Configuration (`/etc/httpd/conf.d/gallery.conf`):**

Create or modify an Apache configuration file:

```
# /etc/httpd/conf.d/gallery.conf
<VirtualHost *:443> # Listening on HTTPS port 443
    ServerName your_domain_or_server_ip # e.g., example.com

    # SSL/TLS Configuration (adjust paths to your Let's Encrypt certificates)
    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/your_domain_or_server_ip/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/your_domain_or_server_ip/privkey.pem
    # Add any other SSL directives from your existing config here

    ProxyPreserveHost On
    ProxyRequests Off

    ErrorLog /var/log/httpd/gallery_error.log
    CustomLog /var/log/httpd/gallery_access.log combined

    # --- Centralized HTTP Basic Authentication and Proxying for the Gallery ---
    # SCRIPT_NAME in the container should be '/'
    # The external prefix (e.g., /gallery) is handled by Apache.
    # IMPORTANT: Replace <EXTERNAL_URL_PREFIX> with your actual external path (e.g., /gallery)
    #            Replace <container_name> with your container's name (e.g., pygallery-app)
    <Location /<EXTERNAL_URL_PREFIX>>
        AuthType Basic
        AuthName "Restricted Gallery Access"
        AuthUserFile /etc/httpd/.htpasswd # **UPDATE THIS PATH**
        Require valid-user

        # Tell backend Flask app about original client request context
        RequestHeader set X-Forwarded-Proto "https"
        RequestHeader set X-Forwarded-Ssl "on"
        RequestHeader set X-Forwarded-Port "443"
        RequestHeader set X-Forwarded-Host your_domain_or_server_ip # **UPDATE THIS**
        RequestHeader set X-Forwarded-Prefix "/<EXTERNAL_URL_PREFIX>" # Tells Flask its external mount point

        # Proxy requests to the container's internal root '/'
        # Flask is configured to run at internal root '/' and uses SCRIPT_NAME for external URL generation.
        ProxyPass http://<container_name>:5000/ nocanon
        ProxyPassReverse http://<container_name>:5000/
        # ProxyPassReverseCookieDomain <container_name> your_domain_or_server_ip # Uncomment if cookies involved
        # ProxyPassReverseCookiePath / /<EXTERNAL_URL_PREFIX>/ # Uncomment if cookies involved

    </Location>
    <Directory />
        Require all granted
    </Directory>
</VirtualHost>

```

**Remember to:**

* Replace all placeholders (`<EXTERNAL_URL_PREFIX>`, `your_domain_or_server_ip`, `<container_name>`, and SSL certificate/key paths).

## Customization

* **Gallery Display Mode:** Set `Environment=GALLERY_MODE=FLAT_ROOT_DISPLAY` in your `photo-gallery.container` Quadlet file for direct display of root photos (if no subfolders exist). Use `ALBUM_DISPLAY` (default) for the album list view.

* **Thumbnail Size:** Adjust `THUMBNAIL_SIZE` in `config.ini`.

* **Styling:** Modify `static/css/style.css` for visual changes.

* **Flask Routes:** Extend or modify routes in `app.py` for new features.

## Contributing

Feel free to fork this repository, open issues, or submit pull requests.

## License

This project is licensed under the MIT License.
