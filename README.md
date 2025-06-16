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

---

## Generating Dummy Images (Optional)

For testing purposes, you can use the provided script to generate some placeholder images:

```bash
python generate_dummy_images.py
```
This will create `photos/VacationPhotos` and `photos/Cityscapes` with sample images.

---

## Running the Application

### 1. Local Development (Python)

To run the Flask application directly (for development):

```bash
python app.py
```
Access the gallery at `http://127.0.0.1:5000/gallery/` (or the port specified in `config.ini`).

### 2. Containerized Deployment (Podman/Docker)

**Build the Image:**

```bash
# Using Podman
podman build -t pygallery .

# Using Docker
docker build -t pygallery .
```

**Run the Container (for testing, or if not using Quadlet/Apache):**

```bash
# Replace /path/to/your/actual/photos and /path/to/your/actual/thumbnails
# with your actual host directories.
HOST_PHOTOS_DIR="/home/user/my_gallery_photos"
HOST_THUMBNAILS_DIR="/home/user/my_gallery_thumbnails"

# Using Podman
podman run -d \
  --name pygallery-app \
  -p 8000:5000 \
  -v "${HOST_PHOTOS_DIR}":/app/photos:Z \
  -v "${HOST_THUMBNAILS_DIR}":/app/thumbnails:Z \
  pygallery

# Using Docker
docker run -d \
  --name pygallery-app \
  -p 8000:5000 \
  -v "${HOST_PHOTOS_DIR}":/app/photos \
  -v "${HOST_THUMBNAILS_DIR}":/app/thumbnails \
  pygallery
```
Access the gallery at `http://your_server_ip:8000/gallery/`.

### 3. Deployment with Quadlet (Systemd Service on Fedora)

Quadlet allows you to manage your container as a systemd service.

**1. Place the Quadlet File:**

Save the `pygallery-app.container` file to `/etc/containers/systemd/`:

```ini
# /etc/containers/systemd/pygallery-app.container
[Container]
ContainerName=pygallery-app
Image=localhost/pygallery:latest
Volume=/home/user/my_gallery_photos:/app/photos:Z # **UPDATE THIS PATH**
Volume=/home/user/my_gallery_thumbnails:/app/thumbnails:Z # **UPDATE THIS PATH**
PublishPort=8000:5000 # Container port 5000 mapped to host port 8000
Restart=on-failure

[Unit]
Description=pygallery: My Lightweight Photo Gallery Container
Wants=network-online.target
After=network-online.target
```
**Remember to replace the volume paths** with your actual host directories.

**2. Reload Systemd and Start Service:**

```bash
sudo systemctl daemon-reload
sudo systemctl start pygallery-app.service
sudo systemctl enable pygallery-app.service # To start on boot
```
Access the gallery at `http://your_server_ip:8000/gallery/`.

### 4. Deploying with Apache Reverse Proxy at `/gallery`

If Apache is already running on port 80, you can use it as a reverse proxy to serve your gallery at `example.com/gallery`.

**1. Ensure Container is Running (Internal Port Only):**

Your `pygallery-app.container` file (or `podman run` command) **should not** publish port 80 or 8000 to the host if Apache is handling the public-facing access. It only needs to listen on port 5000 internally. You can remove `PublishPort` from your Quadlet file or bind it to `127.0.0.1` for internal testing: `PublishPort=127.0.0.1:8080:5000`.

**2. Apache Configuration (`/etc/httpd/conf.d/gallery.conf`):**

Create or modify an Apache configuration file:

```apacheconf
# /etc/httpd/conf.d/gallery.conf
<VirtualHost *:80>
    ServerName your_domain_or_server_ip # e.g., example.com

    ProxyPreserveHost On
    ProxyRequests Off

    # Get container's internal IP with: podman inspect pygallery-app | grep -i "IPAddress"
    # Example IP: 172.17.0.2 (this will vary)
    ProxyPass /gallery/ http://<container_internal_ip>:5000/gallery/ nocanon
    ProxyPassReverse /gallery/ http://<container_internal_ip>:5000/gallery/

    ErrorLog /var/log/httpd/gallery_error.log
    CustomLog /var/log/httpd/gallery_access.log combined

    <Directory />
        Require all granted
    </Directory>
</VirtualHost>
```
**Remember to replace `<container_internal_ip>`** with the actual internal IP address of your running Podman container.

**3. Adjust SELinux (if necessary):**

```bash
sudo setsebool -P httpd_can_network_connect 1
```

**4. Restart Apache:**

```bash
sudo systemctl restart httpd
```

Your gallery should now be accessible at `http://your_domain_or_server_ip/gallery/`.

---

## Customization

* **Thumbnail Size:** Adjust `THUMBNAIL_SIZE` in `config.ini`.
* **Styling:** Modify `static/css/style.css` for visual changes.
* **Flask Routes:** Extend or modify routes in `app.py` for new features.

---

## Contributing

Feel free to fork this repository, open issues, or submit pull requests.

---

## License

This project is licensed under the MIT License.

