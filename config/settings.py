# config/settings.py
"""Configuration management for pygallery."""

import os
import configparser
from pathlib import Path
from typing import Dict, Any


class Config:
    """Configuration class for pygallery."""
    
    def __init__(self, config_file: str = 'config.ini'):
        self.config_file = config_file
        self.app_config: Dict[str, Any] = {}
        self.load_config()
    
    def load_config(self) -> None:
        """Loads configuration from config.ini."""
        if not os.path.exists(self.config_file):
            print(f"Error: Configuration file '{self.config_file}' not found.")
            print("Please create a config.ini with [Gallery] section and PHOTOS_DIR, THUMBNAILS_DIR, THUMBNAIL_SIZE, PORT.")
            exit(1)

        config = configparser.ConfigParser()
        config.read(self.config_file)

        if 'Gallery' not in config:
            print(f"Error: 'Gallery' section not found in '{self.config_file}'.")
            exit(1)

        try:
            self.app_config['PHOTOS_DIR'] = Path(config['Gallery'].get('PHOTOS_DIR', './photos')).resolve()
            self.app_config['THUMBNAILS_DIR'] = Path(config['Gallery'].get('THUMBNAILS_DIR', './thumbnails')).resolve()
            self.app_config['THUMBNAIL_SIZE'] = tuple(map(int, config['Gallery'].get('THUMBNAIL_SIZE', '200,200').split(',')))
            self.app_config['PORT'] = int(config['Gallery'].get('PORT', '5000'))
        except ValueError as e:
            print(f"Error parsing configuration: {e}")
            exit(1)

        print(f"Configuration loaded: {self.app_config}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        return self.app_config.get(key, default)
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values."""
        return self.app_config.copy()


# Global configuration instance
config = Config() 