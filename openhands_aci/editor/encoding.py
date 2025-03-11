"""Encoding management for file operations."""

import functools
import os
from pathlib import Path


class EncodingManager:
    """Manages file encodings across multiple operations to ensure consistency."""

    def __init__(self):
        # Cache detected encodings to avoid repeated detection on the same file
        # Format: {path_str: (encoding, mtime)}
        self._encoding_cache = {}
        # Default fallback encoding
        self.default_encoding = 'utf-8'
        # Confidence threshold for encoding detection
        self.confidence_threshold = 0.7

    def detect_encoding(self, path: Path) -> str:
        """Detect the encoding of a file and cache the result.

        Args:
            path: Path to the file

        Returns:
            The detected encoding or default encoding if detection fails
        """
        path_str = str(path)
        current_mtime = os.path.getmtime(path) if path.exists() else 0

        # Return cached encoding if available and file hasn't been modified
        if path_str in self._encoding_cache:
            cached_encoding, cached_mtime = self._encoding_cache[path_str]
            if cached_mtime == current_mtime:
                return cached_encoding

        # Use chardet to detect encoding
        import chardet

        # Read a sample of the file to detect encoding
        # Reading the whole file could be slow for large files
        sample_size = min(os.path.getsize(path), 1024 * 1024)  # Max 1MB sample
        with open(path, 'rb') as f:
            raw_data = f.read(sample_size)

        result = chardet.detect(raw_data)

        # Use detected encoding if confidence is high enough, otherwise fallback
        encoding = (
            result['encoding']
            if (result['encoding'] and result['confidence'] > self.confidence_threshold)
            else self.default_encoding
        )

        # Cache the result with current modification time
        self._encoding_cache[path_str] = (encoding, current_mtime)
        return encoding

    def get_encoding(self, path: Path) -> str:
        """Get encoding for a file, detecting if necessary.

        Args:
            path: Path to the file

        Returns:
            The encoding for the file
        """
        path_str = str(path)

        # If file doesn't exist, return default encoding
        if not path.exists():
            return self.default_encoding

        # If file exists but not in cache or mtime changed, detect encoding
        if path_str not in self._encoding_cache:
            return self.detect_encoding(path)

        # Check if the file has been modified since last detection
        current_mtime = os.path.getmtime(path)
        cached_encoding, cached_mtime = self._encoding_cache[path_str]

        if current_mtime != cached_mtime:
            # File has been modified, re-detect encoding
            return self.detect_encoding(path)

        return cached_encoding

    def set_encoding(self, path: Path, encoding: str) -> None:
        """Manually set encoding for a file.

        Args:
            path: Path to the file
            encoding: Encoding to set
        """
        current_mtime = os.path.getmtime(path) if path.exists() else 0
        self._encoding_cache[str(path)] = (encoding, current_mtime)

    def clear_cache(self, path: Path | None = None) -> None:
        """Clear encoding cache for a specific file or all files.

        Args:
            path: Path to the file to clear from cache, or None to clear all
        """
        if path:
            self._encoding_cache.pop(str(path), None)
        else:
            self._encoding_cache.clear()


def with_encoding(method):
    """Decorator to handle file encoding for file operations.

    This decorator automatically detects and applies the correct encoding
    for file operations, ensuring consistency between read and write operations.

    Args:
        method: The method to decorate

    Returns:
        The decorated method
    """

    @functools.wraps(method)
    def wrapper(self, path: Path, *args, **kwargs):
        # Skip encoding handling for directories
        if path.is_dir():
            return method(self, path, *args, **kwargs)

        # For files that don't exist yet (like in 'create' command),
        # use the default encoding
        if not path.exists():
            if 'encoding' not in kwargs:
                kwargs['encoding'] = self._encoding_manager.default_encoding
        else:
            # Get encoding from the encoding manager for existing files
            encoding = self._encoding_manager.get_encoding(path)

            # Add encoding to kwargs if the method accepts it
            if 'encoding' not in kwargs:
                kwargs['encoding'] = encoding

        return method(self, path, *args, **kwargs)

    return wrapper
