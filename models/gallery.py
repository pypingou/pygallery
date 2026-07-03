# models/gallery.py
"""Gallery model with core business logic for pygallery."""

import os
from pathlib import Path
from typing import List, Dict, Any
from flask import url_for
import traceback
import logging

from config.settings import config
from utils.image_processing import is_image_file, is_video_file, get_or_create_thumbnail, get_or_create_video_thumbnail
from utils.security import validate_album_name, safe_path_join, SecurityError, sanitize_error_message


class Gallery:
    """Core gallery model handling albums and photos."""
    
    def __init__(self):
        self.photos_root = config.get('PHOTOS_DIR')
        self.thumbnails_root = config.get('THUMBNAILS_DIR')
        self.thumbnail_size = config.get('THUMBNAIL_SIZE')
    
    def get_photos_for_path(self, fs_path: Path, album_name_for_url: str) -> List[Dict[str, Any]]:
        """
        Helper to list photos and videos for a given filesystem path and construct their URLs.

        Args:
            fs_path: Filesystem path to scan for media files
            album_name_for_url: Name used in Flask URL routing (e.g., '__root__' or 'folder/sub')

        Returns:
            List of media dictionaries with URLs and metadata
        """
        media_list = []

        if not fs_path.is_dir():
            logging.debug(f"get_photos_for_path: Filesystem path not found or not a directory: {sanitize_error_message(str(fs_path))}")
            return []

        try:
            for filename in os.listdir(fs_path):
                file_path = fs_path / filename
                if not file_path.is_file():
                    continue

                media_type = None
                relative_to_photos_root = file_path.relative_to(self.photos_root)
                filename_for_url_arg = str(relative_to_photos_root).replace(os.sep, '/')

                if is_image_file(filename):
                    # Process image
                    media_type = 'image'
                    thumbnail_path = self.thumbnails_root / relative_to_photos_root
                    get_or_create_thumbnail(file_path, thumbnail_path, self.thumbnail_size)
                    thumb_url = url_for('gallery.serve_thumbnail', filename=filename_for_url_arg, _external=True)

                elif is_video_file(filename):
                    # Process video
                    media_type = 'video'
                    # Video thumbnails are saved as .jpg
                    relative_thumbnail_path = relative_to_photos_root.parent / f"{Path(filename).stem}.jpg"
                    thumbnail_path = self.thumbnails_root / relative_thumbnail_path
                    get_or_create_video_thumbnail(file_path, thumbnail_path, self.thumbnail_size)

                    # Thumbnail URL uses .jpg extension
                    thumb_filename_for_url = str(relative_thumbnail_path).replace(os.sep, '/')
                    thumb_url = url_for('gallery.serve_thumbnail', filename=thumb_filename_for_url, _external=True)

                if media_type:
                    original_url = url_for('gallery.serve_photo', filename=filename_for_url_arg, _external=True)

                    media_list.append({
                        "original_filename": filename,
                        "original_url": original_url,
                        "thumbnail_url": thumb_url,
                        "media_type": media_type
                    })

            media_list.sort(key=lambda x: x['original_filename'].lower())
            logging.debug(f"get_photos_for_path: Found {len(media_list)} media files in {sanitize_error_message(str(fs_path))}")
            return media_list
        except Exception as e:
            logging.error(f"Error in get_photos_for_path for {sanitize_error_message(str(fs_path))}: {e}")
            traceback.print_exc()
            return []
    
    def get_albums_data(self) -> Dict[str, Any]:
        """
        Returns a dictionary indicating gallery mode (flat or nested) and album/photo data.
        
        Returns:
            Dictionary with mode and albums/photos data
        """
        logging.info("API albums requested")
        logging.debug(f"PHOTOS_DIR: {self.photos_root}")
        
        albums_list = []
        
        # Read GALLERY_MODE from environment variable
        gallery_mode = os.environ.get('GALLERY_MODE', 'ALBUM_DISPLAY')  # Default to album display

        if not self.photos_root.is_dir():
            logging.error(f"PHOTOS_DIR '{self.photos_root}' does not exist or is not a directory. Returning empty response.")
            return {"mode": "nested_gallery", "albums": []}

        # Determine if it's a flat gallery (only root photos, no sub-albums with photos)
        is_flat_gallery = False
        root_photos_count = 0
        nested_albums_count = 0

        # Walk through the directories to count media files and albums
        for dirpath, dirnames, filenames in os.walk(self.photos_root, topdown=True):
            current_dir_media = [f for f in filenames if is_image_file(f) or is_video_file(f)]

            if Path(dirpath) == self.photos_root:  # Root directory
                root_photos_count = len(current_dir_media)
            elif current_dir_media:  # Any subdirectory with media
                nested_albums_count += 1

        # Define flat gallery criteria: media in root, and no other media-containing subdirectories
        if root_photos_count > 0 and nested_albums_count == 0:
            is_flat_gallery = True

        # Conditional Response based on GALLERY_MODE
        if gallery_mode == 'FLAT_ROOT_DISPLAY' and is_flat_gallery:
            logging.info("Detected FLAT_ROOT_DISPLAY mode. Serving root photos directly.")
            root_photos_data = self.get_photos_for_path(self.photos_root, '__root__')
            return {"mode": "flat_gallery", "photos": root_photos_data}
        else:
            logging.info("Detected NESTED_GALLERY mode or FLAT_ROOT_DISPLAY disabled. Serving album list.")
            # Rebuild albums_list logic for nested/default display
            found_albums_data = {}
            
            for dirpath, dirnames, filenames in os.walk(self.photos_root):
                current_dir_media = [f for f in filenames if is_image_file(f) or is_video_file(f)]

                if current_dir_media:
                    try:
                        relative_path = Path(dirpath).relative_to(self.photos_root)
                        album_name_key = str(relative_path).replace(os.sep, '/')

                        # Try to use first image for cover, fall back to video if no images
                        first_image = next((f for f in filenames if is_image_file(f)), None)
                        first_video = next((f for f in filenames if is_video_file(f)), None)

                        if first_image:
                            cover_filename = first_image
                            cover_path = Path(dirpath) / first_image
                            thumbnail_filename = first_image
                        elif first_video:
                            cover_filename = first_video
                            cover_path = Path(dirpath) / first_video
                            # Video thumbnails use .jpg extension
                            thumbnail_filename = f"{Path(first_video).stem}.jpg"
                        else:
                            continue  # No media found

                        album_thumbnail_dir = self.thumbnails_root / relative_path
                        cover_thumbnail_path = album_thumbnail_dir / thumbnail_filename

                        # Generate thumbnail based on media type
                        if first_image:
                            get_or_create_thumbnail(cover_path, cover_thumbnail_path, self.thumbnail_size)
                        elif first_video:
                            get_or_create_video_thumbnail(cover_path, cover_thumbnail_path, self.thumbnail_size)

                        # Correct filename construction for url_for to handle root album
                        serve_filename_for_url = thumbnail_filename if album_name_key == '.' else f"{album_name_key}/{thumbnail_filename}"
                        cover_thumbnail_url = url_for('gallery.serve_thumbnail', filename=serve_filename_for_url, _external=True)

                        # Map '.' to '__root__' for external facing album name
                        album_name_for_url = '__root__' if album_name_key == '.' else album_name_key

                        found_albums_data[album_name_key] = {
                            "name": album_name_for_url,
                            "display_name": album_name_key if album_name_key != '.' else 'Root Gallery',
                            "cover_thumbnail_url": cover_thumbnail_url,
                            "photo_count": len(current_dir_media)
                        }
                    except Exception as e:
                        logging.error(f"Error processing album directory {sanitize_error_message(str(dirpath))}: {e}")
                        traceback.print_exc()
            
            albums_list = list(found_albums_data.values())
            albums_list.sort(key=lambda x: x['display_name'].lower())
            
            logging.info(f"API albums response: Found {len(albums_list)} albums in nested mode.")
            return {"mode": "nested_gallery", "albums": albums_list}
    
    def get_album_photos(self, album_name: str) -> List[Dict[str, Any]]:
        """
        Get photos for a specific album.
        
        Args:
            album_name: Album name ('__root__' for root album or path like 'folder/sub')
            
        Returns:
            List of photo dictionaries
            
        Raises:
            SecurityError: If album name is invalid
        """
        # Validate album name (this will also handle '__root__' case)
        sanitized_album_name = validate_album_name(album_name)
        
        if sanitized_album_name == '__root__':
            return self.get_photos_for_path(self.photos_root, '__root__')
        else:
            # Use safe path join to prevent directory traversal
            album_path = safe_path_join(self.photos_root, sanitized_album_name)
            return self.get_photos_for_path(album_path, sanitized_album_name)


# Global gallery instance
gallery = Gallery() 