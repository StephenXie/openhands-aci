"""Tests for file operations."""

import os
from pathlib import Path

import pytest

from openhands_aci.editor.file_ops import (
    FileTooLargeError,
    InvalidFileTypeError,
    find_in_file,
    read_file_range,
    replace_in_file,
    validate_text_file,
)


@pytest.fixture
def text_file(tmp_path):
    """Create a test text file."""
    content = '\n'.join(f'Line {i}' for i in range(1, 101))
    path = tmp_path / 'test.txt'
    path.write_text(content)
    return path


@pytest.fixture
def binary_file(tmp_path):
    """Create a test binary file."""
    path = tmp_path / 'test.bin'
    with open(path, 'wb') as f:
        f.write(os.urandom(1024))
    return path


def test_validate_text_file(text_file):
    """Test text file validation."""
    validate_text_file(text_file)


def test_validate_binary_file(binary_file):
    """Test binary file validation."""
    with pytest.raises(InvalidFileTypeError):
        validate_text_file(binary_file)


def test_validate_large_file(tmp_path, monkeypatch):
    """Test large file validation."""
    # Create a file that appears large
    path = tmp_path / 'large.txt'
    path.touch()
    
    # Mock the file size to be larger than MAX_FILE_SIZE
    class MockStat:
        def __init__(self, *args, **kwargs):
            self.st_size = 2 * 1024 * 1024 * 1024
            self.st_mode = 0o100644  # Regular file mode
    
    monkeypatch.setattr(Path, 'stat', MockStat)
    
    with pytest.raises(FileTooLargeError):
        validate_text_file(path)


def test_find_in_file(text_file):
    """Test finding text in file."""
    # Test exact match
    result = find_in_file(text_file, 'Line 50')
    assert result is not None
    line_num, matched = result
    assert line_num == 50
    assert matched == 'Line 50\n'
    
    # Test non-existent text
    result = find_in_file(text_file, 'NonexistentText')
    assert result is None


def test_read_file_range(text_file):
    """Test reading file ranges."""
    # Read specific range
    content = read_file_range(text_file, start_line=10, end_line=12)
    assert content == 'Line 10\nLine 11\nLine 12\n'
    
    # Read from start
    content = read_file_range(text_file, end_line=2)
    assert content == 'Line 1\nLine 2\n'
    
    # Read to end
    content = read_file_range(text_file, start_line=98)
    assert content == 'Line 98\nLine 99\nLine 100\n'


def test_replace_in_file(text_file):
    """Test replacing text in file."""
    # Replace a line
    line_num, matched = replace_in_file(text_file, 'Line 50', 'Modified Line 50')
    assert line_num == 50
    assert matched == 'Line 50\n'
    
    # Verify the change
    content = text_file.read_text()
    assert 'Modified Line 50' in content
    assert 'Line 49' in content
    assert 'Line 51' in content
    
    # Test replacing non-existent text
    with pytest.raises(ValueError):
        replace_in_file(text_file, 'NonexistentText', 'NewText')


def test_memory_usage_for_large_file(tmp_path):
    """Test memory usage remains constant for large files."""
    import psutil
    import resource
    
    # Set memory limit to 256MB
    memory_limit = 256 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
    
    # Create a large file (10MB)
    path = tmp_path / 'large.txt'
    file_size = 10 * 1024 * 1024
    chunk_size = 1024 * 1024  # 1MB chunks
    
    with open(path, 'w') as f:
        written = 0
        while written < file_size:
            chunk = 'x' * (chunk_size - 1) + '\n'
            f.write(chunk)
            written += len(chunk)
    
    # Get initial memory usage
    process = psutil.Process()
    initial_memory = process.memory_info().rss
    
    # Perform operations
    try:
        # Find text near end of file
        find_in_file(path, 'x' * 100)
        
        # Read range from middle
        read_file_range(path, start_line=5000, end_line=5100)
        
        # Replace text in middle
        old_str = 'x' * 100
        new_str = 'y' * 100
        replace_in_file(path, old_str, new_str)
        
        # Check memory usage
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be small (allow 10MB for operations)
        assert memory_increase < 10 * 1024 * 1024, (
            f'Memory usage increased by {memory_increase / 1024 / 1024:.1f}MB'
        )
        
    except MemoryError:
        pytest.fail('Memory limit exceeded')
    except Exception as e:
        if 'Cannot allocate memory' in str(e):
            pytest.fail('Memory limit exceeded')
        raise