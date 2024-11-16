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
    Test request_definition LSP request in multilspy with python repository - OpenHands
    """
    params = {
        'code_language': Language.PYTHON,
        'repo_url': 'https://github.com/All-Hands-AI/OpenHands/',
        'repo_commit': '97f3249205e25abafc13e2c42037dd9b309fbe73',
    }
    with create_test_context(params) as context:
        lsp = LanguageServer.create(
            context.config, context.logger, context.source_directory
        )

        async with lsp.start_server():
            result = await lsp.request_definition(
                str(PurePath('openhands/controller/agent_controller.py')),
                113,
                30,  # self.event_stream.subscribe()
            )

            assert isinstance(result, list)
            assert len(result) == 1
            item = result[0]
            assert item['relativePath'] == str(PurePath('openhands/events/stream.py'))
            assert item['range'] == {
                'start': {'line': 151, 'character': 8},
                'end': {'line': 151, 'character': 17},
            }


@pytest.mark.asyncio
async def test_multilspy_request_references():
    """
    Test request_references LSP request in multilspy with python repository - OpenHands
    """
    params = {
        'code_language': Language.PYTHON,
        'repo_url': 'https://github.com/All-Hands-AI/OpenHands/',
        'repo_commit': '97f3249205e25abafc13e2c42037dd9b309fbe73',
    }
    with create_test_context(params) as context:
        lsp = LanguageServer.create(
            context.config, context.logger, context.source_directory
        )

        async with lsp.start_server():
            result = await lsp.request_references(
                str(PurePath('openhands/controller/agent_controller.py')),
                436,
                16,  # async def _step(self) -> None:
            )

            assert isinstance(result, list)
            assert len(result) == 7

            for item in result:
                del item['uri']
                del item['absolutePath']

            assert result == [
                {
                    'relativePath': str(
                        PurePath('openhands/controller/agent_controller.py')
                    ),
                    'range': {
                        'start': {'line': 201, 'character': 27},
                        'end': {'line': 201, 'character': 32},
                    },
                },
                {
                    'relativePath': str(
                        PurePath('openhands/controller/agent_controller.py')
                    ),
                    'range': {
                        'start': {'line': 436, 'character': 14},
                        'end': {'line': 436, 'character': 19},
                    },
                },
                {
                    'relativePath': str(
                        PurePath('openhands/controller/agent_controller.py')
                    ),
                    'range': {
                        'start': {'line': 534, 'character': 28},
                        'end': {'line': 534, 'character': 33},
                    },
                },
                {
                    'relativePath': str(
                        PurePath('tests/unit/test_agent_controller.py')
                    ),
                    'range': {
                        'start': {'line': 292, 'character': 21},
                        'end': {'line': 292, 'character': 26},
                    },
                },
                {
                    'relativePath': str(
                        PurePath('tests/unit/test_agent_controller.py')
                    ),
                    'range': {
                        'start': {'line': 311, 'character': 21},
                        'end': {'line': 311, 'character': 26},
                    },
                },
                {
                    'relativePath': str(
                        PurePath('tests/unit/test_agent_controller.py')
                    ),
                    'range': {
                        'start': {'line': 332, 'character': 21},
                        'end': {'line': 332, 'character': 26},
                    },
                },
                {
                    'relativePath': str(
                        PurePath('tests/unit/test_agent_controller.py')
                    ),
                    'range': {
                        'start': {'line': 352, 'character': 21},
                        'end': {'line': 352, 'character': 26},
                    },
                },
            ]
