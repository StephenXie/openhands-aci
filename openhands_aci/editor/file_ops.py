"""Efficient file operations for the editor."""

import mmap
import os
from pathlib import Path
from typing import Optional, Tuple

import magic

# Maximum file size for full in-memory operations (100MB)
MAX_FULL_READ_SIZE = 100 * 1024 * 1024

# Maximum file size for any operation (1GB)
MAX_FILE_SIZE = 1024 * 1024 * 1024

class FileError(Exception):
    """Base class for file operation errors."""

class FileTooLargeError(FileError):
    """Raised when file size exceeds limits."""

class InvalidFileTypeError(FileError):
    """Raised when file is not a valid text file."""

def validate_text_file(path: Path) -> None:
    """Validate that a file is a text file and within size limits.
    
    Args:
        path: Path to the file to validate
        
    Raises:
        FileTooLargeError: If file size exceeds MAX_FILE_SIZE
        InvalidFileTypeError: If file is not a text file
        FileNotFoundError: If file does not exist
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    size = path.stat().st_size
    if size > MAX_FILE_SIZE:
        raise FileTooLargeError(
            f"File size {size / 1024 / 1024:.1f}MB exceeds maximum allowed size "
            f"{MAX_FILE_SIZE / 1024 / 1024:.1f}MB"
        )
    
    mime = magic.from_file(str(path), mime=True)
    if not mime.startswith('text/'):
        raise InvalidFileTypeError(
            f"File {path} appears to be {mime}, not a text file"
        )

def find_in_file(path: Path, search_str: str) -> Optional[Tuple[int, str]]:
    """Find a string in a file efficiently using memory mapping.
    
    Args:
        path: Path to the file to search
        search_str: String to search for
        
    Returns:
        Tuple of (line number, matched text) if found, None if not found
        The matched text preserves the original line endings
        
    Raises:
        FileTooLargeError: If file size exceeds MAX_FILE_SIZE
        InvalidFileTypeError: If file is not a text file
        ValueError: If search_str appears multiple times
    """
    validate_text_file(path)
    
    occurrences = []
    with open(path, 'rb') as f:
        # Memory map the file
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            # Find all occurrences
            start_pos = 0
            while True:
                pos = mm.find(search_str.encode(), start_pos)
                if pos == -1:
                    break
                
                # Count newlines up to the match position to get line number
                mm.seek(0)
                line_num = mm.read(pos).count(b'\n') + 1
                
                # Extract the matched text with its line ending
                mm.seek(pos)
                matched = mm.read(len(search_str))
                
                # Include the line ending in the match if present
                if mm.read(1) == b'\n':
                    matched += b'\n'
                
                occurrences.append((line_num, matched.decode()))
                start_pos = pos + 1
    
    if not occurrences:
        return None
    
    if len(occurrences) > 1:
        line_numbers = [line for line, _ in occurrences]
        raise ValueError(
            f'Multiple occurrences found in lines {line_numbers}. Please ensure it is unique.'
        )
    
    return occurrences[0]

def read_file_range(path: Path, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Read a range of lines from a file efficiently.
    
    Args:
        path: Path to the file to read
        start_line: First line to read (1-based), if None reads from start
        end_line: Last line to read (1-based), if None reads to end
        
    Returns:
        String containing the requested lines
        
    Raises:
        FileTooLargeError: If file size exceeds MAX_FILE_SIZE
        InvalidFileTypeError: If file is not a text file
    """
    validate_text_file(path)
    
    # For small files, just read the whole thing
    size = path.stat().st_size
    if size <= MAX_FULL_READ_SIZE and not (start_line or end_line):
        return path.read_text()
    
    lines = []
    current_line = 0
    
    with open(path, 'r') as f:
        # Skip lines before start_line
        if start_line:
            for _ in range(start_line - 1):
                next(f, None)
                current_line += 1
        
        # Read requested lines
        for line in f:
            current_line += 1
            if end_line and current_line > end_line:
                break
            if not start_line or current_line >= start_line:
                # Ensure line has newline
                if not line.endswith('\n'):
                    line += '\n'
                lines.append(line)
    
    return ''.join(lines)

def replace_in_file(path: Path, old_str: str, new_str: str) -> Tuple[int, str]:
    """Replace a string in a file efficiently.
    
    This function uses a temporary file to avoid loading the entire file into memory.
    
    Args:
        path: Path to the file to modify
        old_str: String to replace
        new_str: String to replace with
        
    Returns:
        Tuple of (line number where replacement occurred, matched text that was replaced)
        
    Raises:
        FileTooLargeError: If file size exceeds MAX_FILE_SIZE
        InvalidFileTypeError: If file is not a text file
        ValueError: If old_str not found or found multiple times
    """
    # First find the string to replace
    result = find_in_file(path, old_str)
    if not result:
        raise ValueError(f"String not found in {path}")
    
    line_num, matched_text = result
    
    # Create a temporary file
    temp_path = path.with_suffix(path.suffix + '.tmp')
    try:
        with open(path, 'r') as src, open(temp_path, 'w') as dst:
            # Copy content before the match
            for _ in range(line_num - 1):
                dst.write(next(src))
            
            # Skip the old string in source
            next(src)
            
            # Write the new string
            dst.write(new_str)
            if not new_str.endswith('\n'):
                dst.write('\n')
            
            # Copy the rest
            for line in src:
                dst.write(line)
        
        # Replace the original file
        os.replace(temp_path, path)
        return line_num, matched_text
        
    finally:
        # Clean up temp file if something went wrong
        if temp_path.exists():
            temp_path.unlink()