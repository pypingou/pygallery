# Use a lightweight Python base image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
# Using --no-cache-dir to avoid storing cache data in the image layers, reducing image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application code to the working directory
COPY . .

# Create the directories for photos and thumbnails if they don't exist
# These will be used by Flask if volumes are not mounted.
# They are essential placeholders even with volumes, as Flask's Path() will resolve to them.
RUN mkdir -p photos thumbnails

# Expose the port your Flask app runs on (default is 5000 from config.ini)
ARG FLASK_PORT=5000
EXPOSE ${FLASK_PORT}

# Command to run the Flask application using Gunicorn
# IMPORTANT: The SCRIPT_NAME environment variable should match BASE_URL_PREFIX from config.ini
# This tells Gunicorn (and thus Flask) the application's mount point.
# '--forwarded-allow-ips "*"' tells Gunicorn to trust X-Forwarded-* headers from any proxy.
CMD ["gunicorn", \
     "-b", "0.0.0.0:5000", \
     "--workers", "4", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--forwarded-allow-ips", "*", \
     "app:app"]

