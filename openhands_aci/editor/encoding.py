"""Encoding management for file operations."""

import functools
import os
from pathlib import Path


class EncodingManager:
    """Manages file encodings across multiple operations to ensure consistency."""

    def __init__(self):
        # Cache detected encodings to avoid repeated detection on the same file
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

        # Return cached encoding if available
        if path_str in self._encoding_cache:
            return self._encoding_cache[path_str]

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

        # Cache the result
        self._encoding_cache[path_str] = encoding
        return encoding

    def get_encoding(self, path: Path) -> str:
        """Get encoding for a file, detecting if necessary.

        Args:
            path: Path to the file

        Returns:
            The encoding for the file
        """
        path_str = str(path)
        if path_str not in self._encoding_cache:
            return self.detect_encoding(path)
        return self._encoding_cache[path_str]

    def set_encoding(self, path: Path, encoding: str) -> None:
        """Manually set encoding for a file.

        Args:
            path: Path to the file
            encoding: Encoding to set
        """
        self._encoding_cache[str(path)] = encoding

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
