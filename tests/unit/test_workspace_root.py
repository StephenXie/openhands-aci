import os
from pathlib import Path

import pytest

from openhands_aci.editor.editor import OHEditor
from openhands_aci.editor.exceptions import EditorToolParameterInvalidError


def test_workspace_root_as_cwd(tmp_path):
    """Test that workspace_root is used as the current working directory for path suggestions."""
    # Create a workspace root
    workspace_root = tmp_path / 'workspace'
    workspace_root.mkdir()

    # Initialize editor with workspace_root
    editor = OHEditor(workspace_root=str(workspace_root))

    # Test that a relative path suggestion uses the workspace_root
    relative_path = 'test.txt'
    with pytest.raises(EditorToolParameterInvalidError) as exc_info:
        editor(command='view', path=relative_path)

    error_message = str(exc_info.value.message)
    assert 'The path should be an absolute path' in error_message
    assert 'Maybe you meant' in error_message

    # Extract the suggested path from the error message
    suggested_path = error_message.split('Maybe you meant ')[1].strip('?')
    assert Path(suggested_path).is_absolute()
    assert str(workspace_root) in suggested_path


def test_default_cwd_when_no_workspace_root():
    """Test that the current working directory is used when workspace_root is not provided."""
    # Initialize editor without workspace_root
    editor = OHEditor()

    # Test that a relative path suggestion uses the current working directory
    relative_path = 'test.txt'
    with pytest.raises(EditorToolParameterInvalidError) as exc_info:
        editor(command='view', path=relative_path)

    error_message = str(exc_info.value.message)
    assert 'The path should be an absolute path' in error_message
    assert 'Maybe you meant' in error_message

    # Extract the suggested path from the error message
    suggested_path = error_message.split('Maybe you meant ')[1].strip('?')
    assert Path(suggested_path).is_absolute()
    assert os.getcwd() in suggested_path
