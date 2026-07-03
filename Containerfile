# Use a lightweight Python base image
FROM python:3.11-slim-bookworm

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (ffmpeg for video thumbnail generation)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

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
ENV FLASK_PORT=${FLASK_PORT}
EXPOSE ${FLASK_PORT}

# Command to run the Flask application using Gunicorn
# Set SCRIPT_NAME to '/' as the application runs at the root of the container.
# This ensures consistency for Flask's internal routing.
CMD gunicorn -b 0.0.0.0:${FLASK_PORT} --workers 4 --timeout 120 \
    --access-logfile - --error-logfile - --forwarded-allow-ips "*" \
    --env SCRIPT_NAME="/" app:app

