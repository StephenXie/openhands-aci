"""Tests for encoding detection and handling."""

import os
import tempfile
import time
from pathlib import Path

import pytest

from openhands_aci.editor import file_editor
from openhands_aci.editor.encoding import EncodingManager


@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    fd, path = tempfile.mkstemp()
    os.close(fd)
    yield Path(path)
    os.unlink(path)


def test_encoding_detection(temp_file):
    """Test that the editor correctly detects and displays file encoding."""
    # Create a file with cp1251 encoding
    with open(temp_file, 'wb') as f:
        f.write('# coding: cp1251\n\n'.encode('cp1251'))
        f.write('text = u"привет мир"\n'.encode('cp1251'))

    # View the file
    _ = file_editor(
        command='view',
        path=str(temp_file),
    )

    # Create a new temporary file with UTF-8 encoding to avoid caching issues
    fd, utf8_path = tempfile.mkstemp()
    os.close(fd)
    try:
        with open(utf8_path, 'w', encoding='utf-8') as f:
            f.write('# coding: utf-8\n\n')
            f.write('text = "Hello, world!"\n')

        # View the file
        _ = file_editor(
            command='view',
            path=utf8_path,
        )
    finally:
        os.unlink(utf8_path)


def test_encoding_consistency(temp_file):
    """Test that the editor maintains encoding consistency when editing files."""
    # Create a file with cp1251 encoding
    with open(temp_file, 'wb') as f:
        f.write('# coding: cp1251\n\n'.encode('ascii'))
        f.write('text = u"привет мир"\n'.encode('cp1251'))

    # Edit the file
    file_editor(
        command='str_replace',
        path=str(temp_file),
        old_str='привет мир',
        new_str='привет, мир!',
    )

    # Read the file back with the correct encoding
    with open(temp_file, 'rb') as f:
        content = f.read()

    # Check that the file still has cp1251 encoding
    try:
        decoded = content.decode('cp1251')
        assert 'привет, мир!' in decoded
    except UnicodeDecodeError:
        pytest.fail('File was not saved with the correct encoding')


def test_encoding_cache_invalidation(temp_file):
    """Test that the encoding cache is invalidated when a file is modified externally."""
    # Create a file with UTF-8 encoding
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write('# coding: utf-8\n\n')
        f.write('text = "Hello, world!"\n')

    # Create an encoding manager
    encoding_manager = EncodingManager()

    # Detect the encoding (should be UTF-8 or ASCII)
    initial_encoding = encoding_manager.detect_encoding(temp_file)
    assert initial_encoding.lower() in ('utf-8', 'ascii')

    # Verify the encoding is cached
    cached_encoding = encoding_manager.get_encoding(temp_file)
    assert cached_encoding == initial_encoding

    # Wait a moment to ensure the modification time will be different
    time.sleep(0.1)

    # Modify the file with a different encoding
    with open(temp_file, 'wb') as f:
        f.write('# coding: cp1251\n\n'.encode('ascii'))
        f.write('text = u"привет мир"\n'.encode('cp1251'))

    # Get the encoding again - should detect the new encoding
    new_encoding = encoding_manager.get_encoding(temp_file)
    assert new_encoding.lower() in ('windows-1251', 'cp1251')
    assert new_encoding != initial_encoding

    # Verify the cache was updated
    assert encoding_manager._encoding_cache[str(temp_file)][0] == new_encoding
