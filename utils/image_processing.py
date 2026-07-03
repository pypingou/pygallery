# utils/image_processing.py
"""Image processing utilities for pygallery."""

import os
import logging
import subprocess
from pathlib import Path
from typing import Tuple
from PIL import Image, ImageFile

from config.settings import config
from utils.security import validate_file_extension

# Enable loading truncated images (PIL will load as much as possible)
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Supported image file extensions
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp')

# Supported video file extensions
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.webm', '.mkv', '.m4v', '.3gp')


def is_image_file(filename: str) -> bool:
    """Checks if a file has a supported image extension."""
    return validate_file_extension(filename, IMAGE_EXTENSIONS)


def is_video_file(filename: str) -> bool:
    """Checks if a file has a supported video extension."""
    return validate_file_extension(filename, VIDEO_EXTENSIONS)


def is_media_file(filename: str) -> bool:
    """Checks if a file is either an image or video."""
    return is_image_file(filename) or is_video_file(filename)


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


def get_or_create_video_thumbnail(video_path: Path, thumbnail_path: Path, size: Tuple[int, int]) -> bool:
    """
    Generates a thumbnail for a video file using ffmpeg if it doesn't already exist.

    Args:
        video_path: Path to the original video
        thumbnail_path: Path where the thumbnail should be saved
        size: Tuple of (width, height) for the thumbnail

    Returns:
        bool: True if thumbnail was created successfully, False otherwise
    """
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    if thumbnail_path.exists():
        return True  # Thumbnail already exists

    # Create a temporary file for the extracted frame
    temp_frame = thumbnail_path.parent / f"{thumbnail_path.stem}_temp.jpg"

    try:
        # Extract frame at 1 second using ffmpeg
        # -ss 1: seek to 1 second
        # -i: input file
        # -vframes 1: extract only 1 frame
        # -q:v 2: quality (2 is high quality)
        result = subprocess.run(
            [
                'ffmpeg',
                '-ss', '1',  # Seek to 1 second
                '-i', str(video_path),
                '-vframes', '1',  # Extract 1 frame
                '-q:v', '2',  # High quality
                '-y',  # Overwrite output file
                str(temp_frame)
            ],
            capture_output=True,
            timeout=10,
            text=True
        )

        if result.returncode != 0:
            logging.error(f"ffmpeg failed for {video_path}: {result.stderr}")
            return False

        # Resize the extracted frame to thumbnail size using PIL
        if temp_frame.exists():
            with Image.open(temp_frame) as img:
                img.thumbnail(size)
                img.save(thumbnail_path)

            # Clean up temporary file
            temp_frame.unlink()
            logging.debug(f"Generated video thumbnail for {video_path}")
            return True
        else:
            logging.error(f"ffmpeg did not create temp frame for {video_path}")
            return False

    except subprocess.TimeoutExpired:
        logging.error(f"ffmpeg timeout processing video {video_path}")
        if temp_frame.exists():
            temp_frame.unlink()
        return False
    except FileNotFoundError:
        logging.error("ffmpeg not found. Please install ffmpeg to generate video thumbnails.")
        return False
    except Exception as e:
        logging.error(f"Error generating video thumbnail for {video_path}: {e}")
        if temp_frame.exists():
            temp_frame.unlink()
        return False


def scan_and_generate_all_thumbnails() -> None:
    """
    Scans the PHOTOS_DIR for all images and videos and generates missing thumbnails.
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

    total_media = 0
    total_images = 0
    total_videos = 0
    successful_thumbnails = 0
    failed_media = []

    for dirpath, dirnames, filenames in os.walk(photos_root):
        current_dir_images = [f for f in filenames if is_image_file(f)]
        current_dir_videos = [f for f in filenames if is_video_file(f)]

        if current_dir_images or current_dir_videos:
            relative_path = Path(dirpath).relative_to(photos_root)
            album_thumbnail_dir = thumbnails_root / relative_path
            album_thumbnail_dir.mkdir(parents=True, exist_ok=True)  # Ensure album thumbnail dir exists

            # Process images
            for photo_filename in current_dir_images:
                photo_path = Path(dirpath) / photo_filename
                thumbnail_path = album_thumbnail_dir / photo_filename

                if photo_path.is_file():
                    total_media += 1
                    total_images += 1
                    if get_or_create_thumbnail(photo_path, thumbnail_path, thumbnail_size):
                        successful_thumbnails += 1
                    else:
                        failed_media.append(str(photo_path))

            # Process videos
            for video_filename in current_dir_videos:
                video_path = Path(dirpath) / video_filename
                # Video thumbnails are saved as .jpg
                thumbnail_path = album_thumbnail_dir / f"{Path(video_filename).stem}.jpg"

                if video_path.is_file():
                    total_media += 1
                    total_videos += 1
                    if get_or_create_video_thumbnail(video_path, thumbnail_path, thumbnail_size):
                        successful_thumbnails += 1
                    else:
                        failed_media.append(str(video_path))
    
    # Summary logging
    if total_media > 0:
        success_rate = (successful_thumbnails / total_media) * 100
        logging.info(f"Thumbnail generation complete: {successful_thumbnails}/{total_media} successful ({success_rate:.1f}%)")
        logging.info(f"  Images: {total_images}, Videos: {total_videos}")

        if failed_media:
            logging.warning(f"Failed to process {len(failed_media)} files:")
            for failed_file in failed_media[:5]:  # Show first 5 failed files
                logging.warning(f"  - {failed_file}")
            if len(failed_media) > 5:
                logging.warning(f"  ... and {len(failed_media) - 5} more")
    else:
        logging.info("No media files found for thumbnail generation") 