from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from multilspy import LanguageServer
from multilspy.multilspy_config import Language, MultilspyConfig

from openhands_aci.utils.logger import oh_aci_logger as logger


class LSPManager:
    """Manages LSP server instances for different languages"""

    def __init__(self):
        self._servers: dict[Language, LanguageServer] = {}
        self._active_server: Optional[LanguageServer] = None
        self._source_dir = Path.cwd()

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

    def _get_server(self, language: Language) -> LanguageServer:
        if language not in self._servers:
            config = MultilspyConfig(
                code_language=language,
                source_directory=str(self._source_dir),
            )
            self._servers[language] = LanguageServer.create(
                config, logger, str(self._source_dir)
            )
        return self._servers[language]

    @asynccontextmanager
    async def get_server_for_file(self, file_path: Path):
        """Get an LSP server instance for the given file"""
        language = self._get_language(file_path)
        server = self._get_server(language)

        if self._active_server is not None:
            raise RuntimeError('Another LSP server is already active')

        self._active_server = server
        try:
            async with server.start_server():
                yield server
        finally:
            self._active_server = None
