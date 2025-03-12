"""Unit tests for the encoding module."""

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from openhands_aci.editor.encoding import EncodingManager, with_encoding


@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    fd, path = tempfile.mkstemp()
    os.close(fd)
    yield Path(path)
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@pytest.fixture
def encoding_manager():
    """Create an EncodingManager instance for testing."""
    return EncodingManager()


def test_init(encoding_manager):
    """Test initialization of EncodingManager."""
    assert isinstance(encoding_manager, EncodingManager)
    assert encoding_manager._encoding_cache == {}
    assert encoding_manager.default_encoding == 'utf-8'
    assert encoding_manager.confidence_threshold == 0.7


def test_detect_encoding_nonexistent_file(encoding_manager):
    """Test detecting encoding for a nonexistent file."""
    nonexistent_path = Path('/nonexistent/file.txt')
    encoding = encoding_manager.detect_encoding(nonexistent_path)
    assert encoding == encoding_manager.default_encoding


def test_detect_encoding_utf8(encoding_manager, temp_file):
    """Test detecting UTF-8 encoding."""
    # Create a UTF-8 encoded file
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write('Hello, world! UTF-8 encoded text.')

    encoding = encoding_manager.detect_encoding(temp_file)
    assert encoding.lower() in ('utf-8', 'ascii')


def test_detect_encoding_cp1251(encoding_manager, temp_file):
    """Test detecting CP1251 encoding."""
    # Create a CP1251 encoded file with Cyrillic characters
    with open(temp_file, 'wb') as f:
        f.write('Привет, мир! Текст в кодировке CP1251.'.encode('cp1251'))

    encoding = encoding_manager.detect_encoding(temp_file)
    assert encoding.lower() in ('windows-1251', 'cp1251')


def test_detect_encoding_low_confidence(encoding_manager, temp_file):
    """Test fallback to default encoding when confidence is low."""
    # Create a file with mixed encodings to confuse the detector
    with open(temp_file, 'wb') as f:
        f.write(b'\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f')

    # Mock chardet.detect to return low confidence
    with patch('chardet.detect', return_value={'encoding': 'ascii', 'confidence': 0.3}):
        encoding = encoding_manager.detect_encoding(temp_file)
        assert encoding == encoding_manager.default_encoding


def test_detect_encoding_none_result(encoding_manager, temp_file):
    """Test fallback to default encoding when chardet returns None for encoding."""
    with open(temp_file, 'wb') as f:
        f.write(b'\x00\x01\x02\x03')  # Binary data

    # Mock chardet.detect to return None for encoding
    with patch('chardet.detect', return_value={'encoding': None, 'confidence': 0.0}):
        encoding = encoding_manager.detect_encoding(temp_file)
        assert encoding == encoding_manager.default_encoding


def test_get_encoding_cache_hit(encoding_manager, temp_file):
    """Test that get_encoding uses cached values when available."""
    # Create a file
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write('Hello, world!')

    # First call should detect encoding
    with patch.object(
        encoding_manager, 'detect_encoding', return_value='utf-8'
    ) as mock_detect:
        encoding1 = encoding_manager.get_encoding(temp_file)
        assert encoding1 == 'utf-8'
        mock_detect.assert_called_once()

    # Second call should use cache
    with patch.object(
        encoding_manager, 'detect_encoding', return_value='utf-8'
    ) as mock_detect:
        encoding2 = encoding_manager.get_encoding(temp_file)
        assert encoding2 == 'utf-8'
        mock_detect.assert_not_called()


def test_get_encoding_cache_invalidation(encoding_manager, temp_file):
    """Test that cache is invalidated when file is modified."""
    # Create a file
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write('Hello, world!')

    # First call should detect encoding
    encoding1 = encoding_manager.get_encoding(temp_file)
    assert encoding1.lower() in ('utf-8', 'ascii')

    # Wait a moment to ensure modification time will be different
    time.sleep(0.1)

    # Modify the file
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write('Modified content')

    # Mock detect_encoding to verify it's called again
    with patch.object(
        encoding_manager, 'detect_encoding', return_value='utf-8'
    ) as mock_detect:
        encoding2 = encoding_manager.get_encoding(temp_file)
        assert encoding2 == 'utf-8'
        mock_detect.assert_called_once()


def test_set_encoding(encoding_manager, temp_file):
    """Test manually setting encoding for a file."""
    # Create a file
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write('Hello, world!')

    # Set encoding manually
    encoding_manager.set_encoding(temp_file, 'latin-1')

    # Verify the encoding is used
    encoding = encoding_manager.get_encoding(temp_file)
    assert encoding == 'latin-1'


def test_set_encoding_nonexistent_file(encoding_manager):
    """Test setting encoding for a nonexistent file."""
    nonexistent_path = Path('/nonexistent/file.txt')

    # We need to patch both calls to exists() - one in set_encoding and one in get_encoding
    with patch.object(Path, 'exists', side_effect=[False, False]):
        # First call to exists() in set_encoding
        encoding_manager.set_encoding(nonexistent_path, 'latin-1')

        # Second call to exists() in get_encoding
        # The get_encoding method checks if the file exists and returns default_encoding if not
        # We need to patch the _encoding_cache directly to test this behavior
        path_str = str(nonexistent_path)
        assert path_str in encoding_manager._encoding_cache
        cached_encoding, _ = encoding_manager._encoding_cache[path_str]
        assert cached_encoding == 'latin-1'


def test_clear_cache_specific_file(encoding_manager, temp_file):
    """Test clearing cache for a specific file."""
    # Create a file and detect its encoding
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write('Hello, world!')

    encoding_manager.get_encoding(temp_file)
    assert str(temp_file) in encoding_manager._encoding_cache

    # Clear cache for this file
    encoding_manager.clear_cache(temp_file)
    assert str(temp_file) not in encoding_manager._encoding_cache


def test_clear_cache_all(encoding_manager, temp_file):
    """Test clearing the entire cache."""
    # Create a file and detect its encoding
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write('Hello, world!')

    encoding_manager.get_encoding(temp_file)

    # Create another temporary file
    fd, path2 = tempfile.mkstemp()
    os.close(fd)
    try:
        with open(path2, 'w', encoding='utf-8') as f:
            f.write('Another file')

        encoding_manager.get_encoding(Path(path2))
        assert len(encoding_manager._encoding_cache) == 2

        # Clear all cache
        encoding_manager.clear_cache()
        assert len(encoding_manager._encoding_cache) == 0
    finally:
        try:
            os.unlink(path2)
        except FileNotFoundError:
            pass


def test_with_encoding_decorator():
    """Test the with_encoding decorator."""

    # Create a mock class with a method that will be decorated
    class MockEditor:
        def __init__(self):
            self._encoding_manager = EncodingManager()

        @with_encoding
        def read_file(self, path, encoding='utf-8'):
            return f'Reading file with encoding: {encoding}'

    editor = MockEditor()

    # Test with a directory
    with patch.object(Path, 'is_dir', return_value=True):
        with patch.object(
            editor._encoding_manager, 'get_encoding'
        ) as mock_get_encoding:
            result = editor.read_file(Path('/some/dir'))
            assert result == 'Reading file with encoding: utf-8'
            mock_get_encoding.assert_not_called()

    # Test with a nonexistent file
    with patch.object(Path, 'is_dir', return_value=False):
        with patch.object(Path, 'exists', return_value=False):
            result = editor.read_file(Path('/nonexistent/file.txt'))
            assert (
                result
                == f'Reading file with encoding: {editor._encoding_manager.default_encoding}'
            )

    # Test with an existing file
    with patch.object(Path, 'is_dir', return_value=False):
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(
                editor._encoding_manager, 'get_encoding', return_value='latin-1'
            ):
                result = editor.read_file(Path('/existing/file.txt'))
                assert result == 'Reading file with encoding: latin-1'


def test_with_encoding_respects_provided_encoding():
    """Test that the with_encoding decorator respects explicitly provided encoding."""
    # The current implementation of with_encoding always calls get_encoding
    # but doesn't override the provided encoding if it exists in kwargs

    class MockEditor:
        def __init__(self):
            self._encoding_manager = EncodingManager()

        @with_encoding
        def read_file(self, path, encoding='utf-8'):
            return f'Reading file with encoding: {encoding}'

    editor = MockEditor()

    # Test with explicitly provided encoding
    with patch.object(Path, 'is_dir', return_value=False):
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(
                editor._encoding_manager,
                'get_encoding',
                return_value='detected-encoding',
            ):
                result = editor.read_file(Path('/some/file.txt'), encoding='iso-8859-1')
                # The provided encoding should be used, not the detected one
                assert result == 'Reading file with encoding: iso-8859-1'


def test_with_encoding_integration(temp_file):
    """Test the with_encoding decorator with actual file operations."""

    class TestEditor:
        def __init__(self):
            self._encoding_manager = EncodingManager()

        @with_encoding
        def read_content(self, path, encoding='utf-8'):
            with open(path, 'r', encoding=encoding) as f:
                return f.read()

    # Create a file with CP1251 encoding
    test_content = 'Привет, мир!'
    with open(temp_file, 'wb') as f:
        f.write(test_content.encode('cp1251'))

    # Set up the editor and manually set the encoding
    editor = TestEditor()
    editor._encoding_manager.set_encoding(temp_file, 'cp1251')

    # Read the content using the decorated method
    content = editor.read_content(temp_file)
    assert content == test_content
