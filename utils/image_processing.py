# utils/image_processing.py
"""Image processing utilities for pygallery."""

import os
from pathlib import Path
from typing import Tuple
from PIL import Image

from config.settings import config


# Supported image file extensions
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp')


def is_image_file(filename: str) -> bool:
    """Checks if a file has a supported image extension."""
    return filename.lower().endswith(IMAGE_EXTENSIONS)


def get_or_create_thumbnail(image_path: Path, thumbnail_path: Path, size: Tuple[int, int]) -> None:
    """
    Generates a thumbnail for an image if it doesn't already exist.
    
    Args:
        image_path: Path to the original image
        thumbnail_path: Path where the thumbnail should be saved
        size: Tuple of (width, height) for the thumbnail
    """
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    if thumbnail_path.exists():
        return  # Thumbnail already exists
    
    try:
        with Image.open(image_path) as img:
            img.thumbnail(size)
            img.save(thumbnail_path)
    except Exception as e:
        print(f"Error generating thumbnail for {image_path}: {e}")


def scan_and_generate_all_thumbnails() -> None:
    """
    Scans the PHOTOS_DIR for all images and generates missing thumbnails.
    This runs at application startup.
    """
    photos_root = config.get('PHOTOS_DIR')
    thumbnails_root = config.get('THUMBNAILS_DIR')
    thumbnail_size = config.get('THUMBNAIL_SIZE')
    
    print(f"--- Starting initial thumbnail generation scan for '{photos_root}' ---")

    if not photos_root.is_dir():
        print(f"Warning: PHOTOS_DIR '{photos_root}' does not exist or is not a directory. Skipping initial thumbnail scan.")
        return

    thumbnails_root.mkdir(parents=True, exist_ok=True)  # Ensure root thumbnail dir exists

    for dirpath, dirnames, filenames in os.walk(photos_root):
        current_dir_images = [f for f in filenames if is_image_file(f)]
        
        if current_dir_images:
            relative_path = Path(dirpath).relative_to(photos_root)
            album_thumbnail_dir = thumbnails_root / relative_path
            album_thumbnail_dir.mkdir(parents=True, exist_ok=True)  # Ensure album thumbnail dir exists

            for photo_filename in current_dir_images:
                photo_path = Path(dirpath) / photo_filename
                thumbnail_path = album_thumbnail_dir / photo_filename
                
                # Only call get_or_create_thumbnail if it's a file and not already a thumbnail
                if photo_path.is_file():
                    get_or_create_thumbnail(photo_path, thumbnail_path, thumbnail_size)
    
    print("--- Initial thumbnail generation scan complete ---") 