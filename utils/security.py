# utils/security.py
"""Security utilities for pygallery."""

import os
import re
from pathlib import Path
from typing import Optional, Union
from urllib.parse import unquote


class SecurityError(Exception):
    """Custom exception for security-related errors."""
    pass


def validate_path_component(path_component: str) -> str:
    """
    Validate a path component to prevent directory traversal.
    Does NOT sanitize - only validates for security issues.
    
    Args:
        path_component: The path component to validate
        
    Returns:
        Original path component if valid
        
    Raises:
        SecurityError: If path component contains malicious patterns
    """
    if not path_component:
        raise SecurityError("Path component cannot be empty")
    
    # URL decode first
    decoded = unquote(path_component)
    
    # Check for directory traversal attempts
    dangerous_patterns = [
        '..',      # Parent directory
        '~/',      # Home directory (but allow ~ in filenames)
        '//',      # Double slash
        '\\\\',    # Double backslash
        '\x00',    # Null byte
    ]
    
    for pattern in dangerous_patterns:
        if pattern in decoded:
            raise SecurityError(f"Invalid path component: contains '{pattern}'")
    
    # Check for absolute paths
    if decoded.startswith('/') or decoded.startswith('\\'):
        raise SecurityError("Absolute paths are not allowed")
    
    # Check for Windows drive letters at start
    if re.match(r'^[A-Za-z]:[/\\]', decoded):
        raise SecurityError("Drive letters are not allowed")
    
    # Check for control characters (but allow most printable chars)
    if any(ord(c) < 32 and c not in '\t\n\r' for c in decoded):
        raise SecurityError("Control characters are not allowed")
    
    # Return original (decoded) path component without modification
    return decoded


def validate_album_name(album_name: str) -> str:
    """
    Validate album name for security issues.
    
    Args:
        album_name: The album name to validate
        
    Returns:
        Original album name if valid
        
    Raises:
        SecurityError: If album name is invalid
    """
    if not album_name:
        raise SecurityError("Album name cannot be empty")
    
    # Special case for root album
    if album_name == '__root__':
        return album_name
    
    # Split by '/' and validate each component
    components = album_name.split('/')
    validated_components = []
    
    for component in components:
        if not component:  # Skip empty components
            continue
        validated_component = validate_path_component(component)
        validated_components.append(validated_component)
    
    if not validated_components:
        raise SecurityError("Album name has no valid components")
    
    return '/'.join(validated_components)


def validate_filename(filename: str) -> str:
    """
    Validate filename for security issues.
    
    Args:
        filename: The filename to validate
        
    Returns:
        Original filename if valid
        
    Raises:
        SecurityError: If filename is invalid
    """
    if not filename:
        raise SecurityError("Filename cannot be empty")
    
    # URL decode first
    decoded = unquote(filename)
    
    # Check for directory traversal in filename
    if '/' in decoded or '\\' in decoded:
        raise SecurityError("Filename cannot contain directory separators")
    
    # Validate as single path component
    return validate_path_component(decoded)


def safe_path_join(base_path: Path, path_string: str) -> Path:
    """
    Safely join a path string to base_path, ensuring result is within base_path.
    
    Args:
        base_path: The base directory path
        path_string: Path string to join (may contain forward slashes)
        
    Returns:
        Safe joined path
        
    Raises:
        SecurityError: If resulting path is outside base_path
    """
    if not path_string:
        return base_path
    
    # Split the path string and validate each component
    components = path_string.split('/')
    validated_components = []
    
    for component in components:
        if component:  # Skip empty components
            validated = validate_path_component(component)
            validated_components.append(validated)
    
    # Join the components one by one
    result_path = base_path
    for component in validated_components:
        result_path = result_path / component
    
    # Resolve the path to handle any remaining .. or . components
    try:
        resolved_path = result_path.resolve()
        resolved_base = base_path.resolve()
        
        # Check if resolved path is within base directory
        resolved_path.relative_to(resolved_base)
        
        return resolved_path
    except (ValueError, OSError) as e:
        raise SecurityError(f"Invalid path: {path_string}")
    except Exception as e:
        raise SecurityError(f"Path resolution error: {str(e)}")


def validate_file_extension(filename: str, allowed_extensions: tuple) -> bool:
    """
    Validate file extension against allowed extensions.
    
    Args:
        filename: The filename to check
        allowed_extensions: Tuple of allowed extensions (e.g., ('.jpg', '.png'))
        
    Returns:
        True if extension is allowed, False otherwise
    """
    if not filename:
        return False
    
    # Get file extension in lowercase
    file_ext = Path(filename).suffix.lower()
    
    # Check if extension is in allowed list
    return file_ext in allowed_extensions


def sanitize_error_message(message: str) -> str:
    """
    Sanitize error message to prevent information disclosure.
    
    Args:
        message: The error message to sanitize
        
    Returns:
        Sanitized error message
    """
    # Remove potential sensitive information
    sanitized = re.sub(r'/[^/\s]+/[^/\s]+/[^/\s]+', '/***/***/***', message)
    sanitized = re.sub(r'[A-Za-z]:[^\\s]+', 'C:\\***\\***', sanitized)
    
    return sanitized 