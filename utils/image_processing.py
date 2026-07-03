# utils/image_processing.py
"""Image processing utilities for pygallery."""

import os
import logging
from pathlib import Path
from typing import Tuple
from PIL import Image, ImageFile

from config.settings import config
from utils.security import validate_file_extension

# Enable loading truncated images (PIL will load as much as possible)
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Supported image file extensions
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp')


def is_image_file(filename: str) -> bool:
    """Checks if a file has a supported image extension."""
    return validate_file_extension(filename, IMAGE_EXTENSIONS)


def get_or_create_thumbnail(image_path: Path, thumbnail_path: Path, size: Tuple[int, int]) -> bool:
    """
    Generates a thumbnail for an image if it doesn't already exist.
    
    Args:
        image_path: Path to the original image
        thumbnail_path: Path where the thumbnail should be saved
        size: Tuple of (width, height) for the thumbnail
        
    Returns:
        bool: True if thumbnail was created successfully, False otherwise
    """
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    if thumbnail_path.exists():
        return True  # Thumbnail already exists
    
    try:
        with Image.open(image_path) as img:
            # Verify the image by attempting to load it fully
            img.verify()
            
        # Re-open for processing (verify() closes the image)
        with Image.open(image_path) as img:
            img.thumbnail(size)
            img.save(thumbnail_path)
            logging.debug(f"Generated thumbnail for {image_path}")
            return True
            
    except (OSError, IOError) as e:
        if "truncated" in str(e).lower() or "image file is truncated" in str(e).lower():
            logging.warning(f"Image file is corrupted/truncated: {image_path}. Attempting to load partial image.")
            try:
                # Try to load the truncated image anyway
                with Image.open(image_path) as img:
                    img.load()  # Force load what we can
                    img.thumbnail(size)
                    img.save(thumbnail_path)
                    logging.info(f"Successfully created thumbnail from truncated image: {image_path}")
                    return True
            except Exception as e2:
                logging.error(f"Failed to process truncated image {image_path}: {e2}")
                return False
        else:
            logging.error(f"Error processing image {image_path}: {e}")
            return False
    except Exception as e:
        logging.error(f"Unexpected error generating thumbnail for {image_path}: {e}")
        return False


def scan_and_generate_all_thumbnails() -> None:
    """
    Scans the PHOTOS_DIR for all images and generates missing thumbnails.
    This runs at application startup.
    """
    photos_root = config.get('PHOTOS_DIR')
    thumbnails_root = config.get('THUMBNAILS_DIR')
    thumbnail_size = config.get('THUMBNAIL_SIZE')
    
    logging.info(f"Starting initial thumbnail generation scan for '{photos_root}'")

    if not photos_root.is_dir():
        logging.warning(f"PHOTOS_DIR '{photos_root}' does not exist or is not a directory. Skipping initial thumbnail scan.")
        return

    thumbnails_root.mkdir(parents=True, exist_ok=True)  # Ensure root thumbnail dir exists

    total_images = 0
    successful_thumbnails = 0
    failed_images = []

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
                    total_images += 1
                    if get_or_create_thumbnail(photo_path, thumbnail_path, thumbnail_size):
                        successful_thumbnails += 1
                    else:
                        failed_images.append(str(photo_path))
    
    # Summary logging
    if total_images > 0:
        success_rate = (successful_thumbnails / total_images) * 100
        logging.info(f"Thumbnail generation complete: {successful_thumbnails}/{total_images} successful ({success_rate:.1f}%)")
        
        if failed_images:
            logging.warning(f"Failed to process {len(failed_images)} images:")
            for failed_image in failed_images[:5]:  # Show first 5 failed images
                logging.warning(f"  - {failed_image}")
            if len(failed_images) > 5:
                logging.warning(f"  ... and {len(failed_images) - 5} more")
    else:
        logging.info("No images found for thumbnail generation") 