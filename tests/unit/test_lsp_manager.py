from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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


@patch('openhands_aci.editor.editor.LanguageServer')
def test_get_server_creates_new_server(mock_language_server, lsp_manager):
    """Test server creation for a new language"""
    mock_server = MagicMock()
    mock_language_server.create.return_value = mock_server

    server = lsp_manager._get_server(Language.PYTHON)

    assert server == mock_server
    mock_language_server.create.assert_called_once()
    assert Language.PYTHON in lsp_manager._servers


@patch('openhands_aci.editor.editor.LanguageServer')
def test_get_server_reuses_existing_server(mock_language_server, lsp_manager):
    """Test server reuse for the same language"""
    mock_server = MagicMock()
    mock_language_server.create.return_value = mock_server

    # First call creates a new server
    server1 = lsp_manager._get_server(Language.PYTHON)
    # Second call should reuse the same server
    server2 = lsp_manager._get_server(Language.PYTHON)

    assert server1 == server2
    mock_language_server.create.assert_called_once()


@pytest.mark.asyncio
async def test_get_server_for_file_success():
    """Test successful server acquisition for a file"""
    manager = LSPManager()
    mock_server = AsyncMock()

    with patch.object(manager, '_get_server', return_value=mock_server):
        async with manager.get_server_for_file(Path('test.py')) as server:
            assert server == mock_server
            assert manager._active_server == mock_server
            mock_server.start_server.assert_called_once()

        # After context exit, active server should be None
        assert manager._active_server is None


@pytest.mark.asyncio
async def test_get_server_for_file_concurrent_access():
    """Test that concurrent server access is prevented"""
    manager = LSPManager()
    mock_server = AsyncMock()

    with patch.object(manager, '_get_server', return_value=mock_server):
        async with manager.get_server_for_file(Path('test.py')):
            # Try to get another server while one is active
            with pytest.raises(
                RuntimeError, match='Another LSP server is already active'
            ):
                async with manager.get_server_for_file(Path('other.py')):
                    pass


@pytest.mark.asyncio
async def test_get_server_for_file_cleanup_on_error():
    """Test server cleanup when an error occurs"""
    manager = LSPManager()
    mock_server = AsyncMock()
    mock_server.start_server.side_effect = Exception('Server error')

    with patch.object(manager, '_get_server', return_value=mock_server):
        with pytest.raises(Exception, match='Server error'):
            async with manager.get_server_for_file(Path('test.py')):
                pass

        # Active server should be None even after error
        assert manager._active_server is None


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


@pytest.mark.asyncio
async def test_lsp_command_without_old_str(editor, tmp_path):
    """Test LSP commands require old_str parameter"""
    test_file = tmp_path / 'test.py'
    test_file.write_text("def hello():\n    print('world')\n")

    for command in ['jump_to_definition', 'find_references', 'hover']:
        with pytest.raises(EditorToolParameterMissingError, match='old_str'):
            editor(command=command, path=str(test_file))


@pytest.mark.asyncio
async def test_lsp_command_with_old_str(editor, tmp_path):
    """Test LSP commands with valid old_str parameter"""
    test_file = tmp_path / 'test.py'
    test_file.write_text("def hello():\n    print('world')\n")

    mock_result = {'definition': 'test result'}

    with patch.object(editor._lsp_manager, 'get_server_for_file') as mock_get_server:
        mock_server = AsyncMock()
        mock_server.request_definition.return_value = mock_result
        mock_server.request_references.return_value = mock_result
        mock_server.request_hover.return_value = mock_result

        # Mock the async context manager
        mock_get_server.return_value.__aenter__.return_value = mock_server

        # Test each LSP command
        for command in ['jump_to_definition', 'find_references', 'hover']:
            result = editor(command=command, path=str(test_file), old_str='print')
            assert str(mock_result) in result.output
