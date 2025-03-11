"""Tests for encoding detection and handling."""

import os
import tempfile
from pathlib import Path

import pytest

from openhands_aci.editor import file_editor


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
        f.write('# coding: cp1251\n\n'.encode('ascii'))
        f.write('text = u"привет мир"\n'.encode('cp1251'))

    # View the file
    result = file_editor(
        command='view',
        path=str(temp_file),
    )

    # Check that the encoding is detected and displayed
    assert 'File encoding: windows-1251' in result or 'File encoding: cp1251' in result

    # Create a new temporary file with UTF-8 encoding to avoid caching issues
    fd, utf8_path = tempfile.mkstemp()
    os.close(fd)
    try:
        with open(utf8_path, 'w', encoding='utf-8') as f:
            f.write('# coding: utf-8\n\n')
            f.write('text = "Hello, world!"\n')

        # View the file
        result = file_editor(
            command='view',
            path=utf8_path,
        )
    finally:
        os.unlink(utf8_path)

    # For ASCII/UTF-8 files with only ASCII characters, chardet might detect ASCII
    # This is fine since ASCII is a subset of UTF-8
    if 'File encoding:' in result:
        assert 'File encoding: ascii' in result or 'File encoding: utf-8' in result


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
