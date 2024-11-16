from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from multilspy import SyncLanguageServer
from multilspy.multilspy_config import Language, MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger


class LSPManager:
    """Manages LSP server instances for different languages"""

    def __init__(self, workspace_dir: Optional[Path] = None):
        self._servers: dict[Language, SyncLanguageServer] = {}
        self._active_server: Optional[SyncLanguageServer] = None
        self._running_servers: set[SyncLanguageServer] = set()
        self._source_dir = workspace_dir or Path.cwd()
        self._logger = MultilspyLogger()

    def _get_language(self, file_path: Path) -> Language:
        ext = file_path.suffix.lower()
        if ext in ['.py', '.pyi']:
            return Language.PYTHON
        elif ext in ['.js', '.jsx']:
            return Language.JAVASCRIPT
        elif ext in ['.ts', '.tsx']:
            return Language.TYPESCRIPT
        elif ext in ['.java']:
            return Language.JAVA
        elif ext in ['.cs']:
            return Language.CSHARP
        elif ext in ['.rs']:
            return Language.RUST
        else:
            raise ValueError(f'Unsupported file extension for LSP: {ext}')

    def _get_server(self, language: Language) -> SyncLanguageServer:
        if language not in self._servers:
            config = MultilspyConfig(
                code_language=language, trace_lsp_communication=False
            )
            self._servers[language] = SyncLanguageServer.create(
                config, self._logger, str(self._source_dir)
            )
        return self._servers[language]

    def is_running(self, server: SyncLanguageServer) -> bool:
        """Check if a server is currently running"""
        return server in self._running_servers

    @contextmanager
    def get_server_for_file(self, file_path: Path):
        """Get an LSP server instance for the given file"""
        language = self._get_language(file_path)
        server = self._get_server(language)

        if self._active_server is not None:
            raise RuntimeError('Another LSP server is already active')

        self._active_server = server
        try:
            with server.start_server():
                self._running_servers.add(server)
                yield server
        finally:
            self._active_server = None
            if server in self._running_servers:
                self._running_servers.remove(server)
