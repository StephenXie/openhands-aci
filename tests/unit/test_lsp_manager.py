from pathlib import Path

import pytest
from multilspy.multilspy_config import Language

from openhands_aci.editor.editor import LSPManager, OHEditor
from openhands_aci.editor.exceptions import EditorToolParameterMissingError, ToolError


@pytest.fixture
def lsp_manager():
    return LSPManager()


@pytest.fixture
def editor():
    return OHEditor()


def test_get_language_python(lsp_manager):
    """Test language detection for Python files"""
    assert lsp_manager._get_language(Path('test.py')) == Language.PYTHON
    assert lsp_manager._get_language(Path('test.pyi')) == Language.PYTHON


def test_get_language_javascript(lsp_manager):
    """Test language detection for JavaScript/TypeScript files"""
    assert lsp_manager._get_language(Path('test.js')) == Language.JAVASCRIPT
    assert lsp_manager._get_language(Path('test.jsx')) == Language.JAVASCRIPT
    assert lsp_manager._get_language(Path('test.ts')) == Language.TYPESCRIPT
    assert lsp_manager._get_language(Path('test.tsx')) == Language.TYPESCRIPT


def test_get_language_other(lsp_manager):
    """Test language detection for other supported languages"""
    assert lsp_manager._get_language(Path('test.java')) == Language.JAVA
    assert lsp_manager._get_language(Path('test.cs')) == Language.CSHARP
    assert lsp_manager._get_language(Path('test.rs')) == Language.RUST


def test_get_language_unsupported(lsp_manager):
    """Test language detection for unsupported file types"""
    with pytest.raises(ValueError, match='Unsupported file extension for LSP: .txt'):
        lsp_manager._get_language(Path('test.txt'))


def test_get_server_creates_new_server(lsp_manager):
    """Test server creation for a new language"""
    server = lsp_manager._get_server(Language.PYTHON)

    assert server is not None
    # assert isinstance(server, multilspy.language_servers.jedi_language_server.jedi_server.JediServer)
    assert Language.PYTHON in lsp_manager._servers


def test_get_server_reuses_existing_server(lsp_manager):
    """Test server reuse for the same language"""

    # First call creates a new server
    server1 = lsp_manager._get_server(Language.PYTHON)
    # Second call should reuse the same server
    server2 = lsp_manager._get_server(Language.PYTHON)

    assert server1 == server2
    assert Language.PYTHON in lsp_manager._servers


def test_get_server_for_file_success(tmp_path):
    """Test successful server acquisition for a file"""
    manager = LSPManager()
    test_file = tmp_path / 'test.py'
    test_file.write_text("def hello():\n    print('world')\n")

    with manager.get_server_for_file(test_file) as server:
        assert server is not None
        assert manager._active_server == server

    # After context exit, active server should be None
    assert manager._active_server is None


def test_get_server_for_file_concurrent_access(tmp_path):
    """Test that concurrent server access is prevented"""
    manager = LSPManager()
    test_file = tmp_path / 'test.py'
    test_file.write_text("def hello():\n    print('world')\n")

    with manager.get_server_for_file(test_file):
        # Try to get another server while one is active
        with pytest.raises(RuntimeError, match='Another LSP server is already active'):
            with manager.get_server_for_file(test_file):
                pass


def test_get_position_from_str(editor, tmp_path):
    """Test finding position from string in file"""
    test_file = tmp_path / 'test.py'
    content = "def hello():\n    print('world')\n"
    test_file.write_text(content)

    # Test finding string at start of line
    line, char = editor._get_position_from_str(test_file, 'def')
    assert line == 0
    assert char == 0

    # Test finding string with indentation
    line, char = editor._get_position_from_str(test_file, 'print')
    assert line == 1
    assert char == 4

    # Test string not found
    with pytest.raises(ToolError, match='Could not find the string'):
        editor._get_position_from_str(test_file, 'nonexistent')


def test_lsp_command_without_old_str(editor, tmp_path):
    """Test LSP commands require old_str parameter"""
    test_file = tmp_path / 'test.py'
    test_file.write_text("def hello():\n    print('world')\n")

    for command in ['jump_to_definition', 'find_references', 'hover']:
        with pytest.raises(EditorToolParameterMissingError, match='old_str'):
            editor(command=command, path=str(test_file))


def test_lsp_command_with_old_str(tmp_path):
    """Test LSP commands with valid old_str parameter"""
    # Create a small Python project structure
    project_dir = tmp_path / 'project'
    project_dir.mkdir()

    # Create a module with a function
    module_file = project_dir / 'module.py'
    module_file.write_text("""
def greet(name: str) -> str:
    return f"Hello, {name}!"
""")

    # Create a main file that uses the function
    main_file = project_dir / 'main.py'
    main_file.write_text("""
from module import greet

def main():
    message = greet("world")
    print(message)

if __name__ == "__main__":
    main()
""")

    editor = OHEditor(workspace=project_dir)

    # Test jump to definition
    result = editor(command='jump_to_definition', path=str(main_file), old_str='greet')
    assert 'module.py' in result.output

    # Test find references
    result = editor(command='find_references', path=str(module_file), old_str='greet')
    assert 'main.py' in result.output

    # Test hover
    result = editor(command='hover', path=str(module_file), old_str='name')
    assert 'str' in result.output  # Should show type hint info
