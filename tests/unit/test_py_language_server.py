import contextlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Iterator
from uuid import uuid4

import pytest
from multilspy import LanguageServer
from multilspy.multilspy_config import Language, MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger
from multilspy.multilspy_utils import FileUtils


@dataclass
class MultilspyContext:
    config: MultilspyConfig
    logger: MultilspyLogger
    source_directory: str


@contextlib.contextmanager
def create_test_context(params: dict) -> Iterator[MultilspyContext]:
    config = MultilspyConfig.from_dict(params)
    logger = MultilspyLogger()

    user_home_dir = os.path.expanduser('~')
    multilspy_home_directory = str(Path(user_home_dir, '.multilspy'))
    temp_extract_directory = str(Path(multilspy_home_directory, uuid4().hex))
    try:
        os.makedirs(temp_extract_directory, exist_ok=False)
        assert params['repo_url'].endswith('/')
        repo_zip_url = params['repo_url'] + f"archive/{params['repo_commit']}.zip"
        FileUtils.download_and_extract_archive(
            logger, repo_zip_url, temp_extract_directory, 'zip'
        )
        dir_contents = os.listdir(temp_extract_directory)
        assert len(dir_contents) == 1
        source_directory_path = str(Path(temp_extract_directory, dir_contents[0]))

        yield MultilspyContext(config, logger, source_directory_path)
    finally:
        if os.path.exists(temp_extract_directory):
            shutil.rmtree(temp_extract_directory)


@pytest.mark.asyncio
async def test_multilspy_request_definition():
    """
    Test request_definition LSP request in multilspy with python repository - black
    """
    params = {
        'code_language': Language.PYTHON,
        'repo_url': 'https://github.com/psf/black/',
        'repo_commit': 'f3b50e466969f9142393ec32a4b2a383ffbe5f23',
    }
    with create_test_context(params) as context:
        lsp = LanguageServer.create(
            context.config, context.logger, context.source_directory
        )

        async with lsp.start_server():
            result = await lsp.request_definition(
                str(PurePath('src/black/mode.py')), 163, 4
            )

            assert isinstance(result, list)
            assert len(result) == 1
            item = result[0]
            assert item['relativePath'] == str(PurePath('src/black/mode.py'))
            assert item['range'] == {
                'start': {'line': 163, 'character': 4},
                'end': {'line': 163, 'character': 20},
            }


@pytest.mark.asyncio
async def test_multilspy_request_references():
    """
    Test request_references LSP request in multilspy with python repository - black
    """
    params = {
        'code_language': Language.PYTHON,
        'repo_url': 'https://github.com/psf/black/',
        'repo_commit': 'f3b50e466969f9142393ec32a4b2a383ffbe5f23',
    }
    with create_test_context(params) as context:
        lsp = LanguageServer.create(
            context.config, context.logger, context.source_directory
        )

        async with lsp.start_server():
            result = await lsp.request_references(
                str(PurePath('src/black/mode.py')), 163, 4
            )

            assert isinstance(result, list)
            assert len(result) == 8

            for item in result:
                del item['uri']
                del item['absolutePath']

            assert result == [
                {
                    'relativePath': str(PurePath('src/black/__init__.py')),
                    'range': {
                        'start': {'line': 71, 'character': 4},
                        'end': {'line': 71, 'character': 20},
                    },
                },
                {
                    'relativePath': str(PurePath('src/black/__init__.py')),
                    'range': {
                        'start': {'line': 1105, 'character': 11},
                        'end': {'line': 1105, 'character': 27},
                    },
                },
                {
                    'relativePath': str(PurePath('src/black/__init__.py')),
                    'range': {
                        'start': {'line': 1113, 'character': 11},
                        'end': {'line': 1113, 'character': 27},
                    },
                },
                {
                    'relativePath': str(PurePath('src/black/mode.py')),
                    'range': {
                        'start': {'line': 163, 'character': 4},
                        'end': {'line': 163, 'character': 20},
                    },
                },
                {
                    'relativePath': str(PurePath('src/black/parsing.py')),
                    'range': {
                        'start': {'line': 7, 'character': 68},
                        'end': {'line': 7, 'character': 84},
                    },
                },
                {
                    'relativePath': str(PurePath('src/black/parsing.py')),
                    'range': {
                        'start': {'line': 37, 'character': 11},
                        'end': {'line': 37, 'character': 27},
                    },
                },
                {
                    'relativePath': str(PurePath('src/black/parsing.py')),
                    'range': {
                        'start': {'line': 39, 'character': 14},
                        'end': {'line': 39, 'character': 30},
                    },
                },
                {
                    'relativePath': str(PurePath('src/black/parsing.py')),
                    'range': {
                        'start': {'line': 44, 'character': 11},
                        'end': {'line': 44, 'character': 27},
                    },
                },
            ]
