import os

import pytest

from openhands_aci.editor.editor import OHEditor
from openhands_aci.editor.exceptions import EditorToolParameterInvalidError


def test_workspace_root_validation(tmp_path):
    """Test that paths outside the workspace_root are rejected."""
    # Create a workspace root and a file inside it
    workspace_root = tmp_path / 'workspace'
    workspace_root.mkdir()
    test_file = workspace_root / 'test.txt'
    test_file.write_text('This is a test file')

    # Create a file outside the workspace
    outside_file = tmp_path / 'outside.txt'
    outside_file.write_text('This file is outside the workspace')

    # Initialize editor with workspace_root
    editor = OHEditor(workspace_root=str(workspace_root))

    # Test accessing a file inside the workspace (should work)
    result = editor(command='view', path=str(test_file))
    assert 'This is a test file' in result.output

    # Test accessing a file outside the workspace (should fail)
    with pytest.raises(EditorToolParameterInvalidError) as exc_info:
        editor(command='view', path=str(outside_file))

    assert 'File access not permitted' in str(exc_info.value.message)
    assert 'You can only access paths inside the workspace' in str(
        exc_info.value.message
    )


def test_directory_traversal_attack(tmp_path):
    """Test that directory traversal attacks are prevented."""
    # Create a workspace root and a file inside it
    workspace_root = tmp_path / 'workspace'
    workspace_root.mkdir()
    test_file = workspace_root / 'test.txt'
    test_file.write_text('This is a test file')

    # Create a file outside the workspace
    outside_file = tmp_path / 'outside.txt'
    outside_file.write_text('This file is outside the workspace')

    # Initialize editor with workspace_root
    editor = OHEditor(workspace_root=str(workspace_root))

    # Test directory traversal attack
    traversal_path = workspace_root / '..' / 'outside.txt'

    with pytest.raises(EditorToolParameterInvalidError) as exc_info:
        editor(command='view', path=str(traversal_path))

    assert 'File access not permitted' in str(exc_info.value.message)


def test_symlink_traversal_attack(tmp_path):
    """Test that symlink-based traversal attacks are prevented."""
    # Skip test on Windows as symlinks might require admin privileges
    if os.name == 'nt':
        pytest.skip('Skipping symlink test on Windows')

    # Create a workspace root and a file inside it
    workspace_root = tmp_path / 'workspace'
    workspace_root.mkdir()
    test_file = workspace_root / 'test.txt'
    test_file.write_text('This is a test file')

    # Create a file outside the workspace
    outside_file = tmp_path / 'outside.txt'
    outside_file.write_text('This file is outside the workspace')

    # Create a symlink inside the workspace that points outside
    symlink_file = workspace_root / 'symlink.txt'
    symlink_file.symlink_to(outside_file)

    # Initialize editor with workspace_root
    editor = OHEditor(workspace_root=str(workspace_root))

    # Test symlink traversal attack
    with pytest.raises(EditorToolParameterInvalidError) as exc_info:
        editor(command='view', path=str(symlink_file))

    assert 'File access not permitted' in str(exc_info.value.message)


def test_no_workspace_root_restriction():
    """Test that when workspace_root is None, no path restrictions are applied."""
    # Initialize editor without workspace_root
    editor = OHEditor()

    # This should not raise an exception for path validation
    # (might raise for other reasons if the path doesn't exist)
    try:
        editor(command='view', path='/etc/passwd')
    except EditorToolParameterInvalidError as e:
        # Make sure the error is not about workspace restriction
        assert 'File access not permitted' not in str(e.message)
        assert 'You can only access paths inside the workspace' not in str(e.message)
