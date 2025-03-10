import os

import pytest

from openhands_aci.editor.editor import OHEditor
from openhands_aci.editor.exceptions import EditorToolParameterInvalidError


@pytest.fixture
def workspace_setup(tmp_path):
    """Set up a workspace with files inside and outside."""
    # Create a workspace root
    workspace_root = tmp_path / 'workspace'
    workspace_root.mkdir()

    # Create files inside the workspace
    inside_file = workspace_root / 'inside.txt'
    inside_file.write_text('This file is inside the workspace')

    inside_dir = workspace_root / 'inside_dir'
    inside_dir.mkdir()
    nested_file = inside_dir / 'nested.txt'
    nested_file.write_text('This is a nested file')

    # Create files outside the workspace
    outside_file = tmp_path / 'outside.txt'
    outside_file.write_text('This file is outside the workspace')

    # Create a symlink inside pointing outside (if not on Windows)
    symlink_file = None
    if os.name != 'nt':
        symlink_file = workspace_root / 'symlink.txt'
        symlink_file.symlink_to(outside_file)

    return {
        'workspace_root': workspace_root,
        'inside_file': inside_file,
        'inside_dir': inside_dir,
        'nested_file': nested_file,
        'outside_file': outside_file,
        'symlink_file': symlink_file,
    }


def test_workspace_view_command(workspace_setup):
    """Test view command with workspace restrictions."""
    editor = OHEditor(workspace_root=str(workspace_setup['workspace_root']))

    # Should be able to view files inside workspace
    result = editor(command='view', path=str(workspace_setup['inside_file']))
    assert 'This file is inside the workspace' in result.output

    # Should be able to view directories inside workspace
    result = editor(command='view', path=str(workspace_setup['inside_dir']))
    assert 'nested.txt' in result.output

    # Should not be able to view files outside workspace
    with pytest.raises(EditorToolParameterInvalidError) as exc_info:
        editor(command='view', path=str(workspace_setup['outside_file']))
    assert 'File access not permitted' in str(exc_info.value.message)

    # Should not be able to use directory traversal
    traversal_path = workspace_setup['workspace_root'] / '..' / 'outside.txt'
    with pytest.raises(EditorToolParameterInvalidError) as exc_info:
        editor(command='view', path=str(traversal_path))
    assert 'File access not permitted' in str(exc_info.value.message)


def test_workspace_create_command(workspace_setup):
    """Test create command with workspace restrictions."""
    editor = OHEditor(workspace_root=str(workspace_setup['workspace_root']))

    # Should be able to create files inside workspace
    new_file = workspace_setup['workspace_root'] / 'new_file.txt'
    result = editor(command='create', path=str(new_file), file_text='New file content')
    assert 'File created successfully' in result.output
    assert new_file.exists()

    # Should not be able to create files outside workspace
    new_outside = workspace_setup['outside_file'].parent / 'new_outside.txt'
    with pytest.raises(EditorToolParameterInvalidError) as exc_info:
        editor(
            command='create', path=str(new_outside), file_text='Should not be created'
        )
    assert 'File access not permitted' in str(exc_info.value.message)
    assert not new_outside.exists()


def test_workspace_str_replace_command(workspace_setup):
    """Test str_replace command with workspace restrictions."""
    editor = OHEditor(workspace_root=str(workspace_setup['workspace_root']))

    # Should be able to edit files inside workspace
    result = editor(
        command='str_replace',
        path=str(workspace_setup['inside_file']),
        old_str='inside the workspace',
        new_str='within the workspace',
    )
    assert 'The file' in result.output
    assert 'has been edited' in result.output
    assert 'within the workspace' in workspace_setup['inside_file'].read_text()

    # Should not be able to edit files outside workspace
    with pytest.raises(EditorToolParameterInvalidError) as exc_info:
        editor(
            command='str_replace',
            path=str(workspace_setup['outside_file']),
            old_str='outside the workspace',
            new_str='modified outside',
        )
    assert 'File access not permitted' in str(exc_info.value.message)
    assert 'outside the workspace' in workspace_setup['outside_file'].read_text()


def test_workspace_insert_command(workspace_setup):
    """Test insert command with workspace restrictions."""
    editor = OHEditor(workspace_root=str(workspace_setup['workspace_root']))

    # Should be able to insert into files inside workspace
    result = editor(
        command='insert',
        path=str(workspace_setup['inside_file']),
        insert_line=1,
        new_str='Inserted line',
    )
    assert 'The file' in result.output
    assert 'has been edited' in result.output
    assert 'Inserted line' in workspace_setup['inside_file'].read_text()

    # Should not be able to insert into files outside workspace
    with pytest.raises(EditorToolParameterInvalidError) as exc_info:
        editor(
            command='insert',
            path=str(workspace_setup['outside_file']),
            insert_line=1,
            new_str='Inserted outside',
        )
    assert 'File access not permitted' in str(exc_info.value.message)
    assert 'Inserted outside' not in workspace_setup['outside_file'].read_text()


def test_workspace_symlink_access(workspace_setup):
    """Test that symlinks pointing outside the workspace are blocked."""
    # Skip test on Windows as symlinks might require admin privileges
    if os.name == 'nt' or workspace_setup['symlink_file'] is None:
        pytest.skip('Skipping symlink test on Windows or if symlink creation failed')

    editor = OHEditor(workspace_root=str(workspace_setup['workspace_root']))

    # Should not be able to access symlinks pointing outside workspace
    with pytest.raises(EditorToolParameterInvalidError) as exc_info:
        editor(command='view', path=str(workspace_setup['symlink_file']))
    assert 'File access not permitted' in str(exc_info.value.message)


def test_no_workspace_restriction(workspace_setup):
    """Test that without workspace_root, all paths are accessible."""
    editor = OHEditor()  # No workspace_root specified

    # Should be able to access files both inside and outside
    result = editor(command='view', path=str(workspace_setup['inside_file']))
    assert 'This file is inside the workspace' in result.output

    # This might fail if the file doesn't exist, but not because of workspace restrictions
    try:
        result = editor(command='view', path=str(workspace_setup['outside_file']))
        assert 'This file is outside the workspace' in result.output
    except EditorToolParameterInvalidError as e:
        # Make sure the error is not about workspace restriction
        assert 'File access not permitted' not in str(e.message)
        assert 'You can only access paths inside the workspace' not in str(e.message)
