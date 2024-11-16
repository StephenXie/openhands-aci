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


@pytest.mark.asyncio
async def test_multilspy_request_hover():
    """
    Test request_hover LSP request in multilspy with python repository - OpenHands
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
            result = await lsp.request_hover(
                str(PurePath('openhands/controller/agent_controller.py')),
                436,
                16,  # async def _step(self) -> None:
            )

            assert isinstance(result, dict)
            assert (
                result.get('contents').get('value')
                == """```python
def _step(self) -> None
```
---
Executes a single step of the parent or delegate agent. Detects stuck agents and limits on the number of iterations and the task budget.
**Full name:** `openhands.controller.agent_controller.AgentController._step`"""
            )


@pytest.mark.asyncio
async def test_multilspy_request_document_symbols():
    """
    Test request_document_symbols LSP request in multilspy with python repository - OpenHands
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
            result = await lsp.request_document_symbols(
                str(PurePath('openhands/controller/action_parser.py'))
            )
            symbol_lists, _ = result
            assert isinstance(symbol_lists, list)
            assert len(symbol_lists) == 16
            assert symbol_lists == [
                {
                    'detail': 'class ABC',
                    'kind': 5,
                    'name': 'ABC',
                    'range': {
                        'start': {'character': 0, 'line': 0},
                        'end': {'character': 35, 'line': 0},
                    },
                    'selectionRange': {
                        'start': {'character': 16, 'line': 0},
                        'end': {'character': 19, 'line': 0},
                    },
                },
                {
                    'detail': 'def abstractmethod',
                    'kind': 12,
                    'name': 'abstractmethod',
                    'range': {
                        'start': {'character': 0, 'line': 0},
                        'end': {'character': 35, 'line': 0},
                    },
                    'selectionRange': {
                        'start': {'character': 21, 'line': 0},
                        'end': {'character': 35, 'line': 0},
                    },
                },
                {
                    'detail': 'class Action',
                    'kind': 5,
                    'name': 'Action',
                    'range': {
                        'start': {'character': 0, 'line': 2},
                        'end': {'character': 42, 'line': 2},
                    },
                    'selectionRange': {
                        'start': {'character': 36, 'line': 2},
                        'end': {'character': 42, 'line': 2},
                    },
                },
                {
                    'detail': 'class ActionParseError',
                    'kind': 5,
                    'name': 'ActionParseError',
                    'range': {
                        'start': {'character': 0, 'line': 5},
                        'end': {'character': 25, 'line': 12},
                    },
                    'selectionRange': {
                        'start': {'character': 6, 'line': 5},
                        'end': {'character': 22, 'line': 5},
                    },
                },
                {
                    'detail': 'def __init__',
                    'kind': 6,
                    'name': '__init__',
                    'range': {
                        'start': {'character': 4, 'line': 8},
                        'end': {'character': 26, 'line': 9},
                    },
                    'selectionRange': {
                        'start': {'character': 8, 'line': 8},
                        'end': {'character': 16, 'line': 8},
                    },
                },
                {
                    'detail': 'self.error = error',
                    'kind': 7,
                    'name': 'error',
                    'range': {
                        'start': {'character': 8, 'line': 9},
                        'end': {'character': 26, 'line': 9},
                    },
                    'selectionRange': {
                        'start': {'character': 13, 'line': 9},
                        'end': {'character': 18, 'line': 9},
                    },
                },
                {
                    'detail': 'def __str__',
                    'kind': 6,
                    'name': '__str__',
                    'range': {
                        'start': {'character': 4, 'line': 11},
                        'end': {'character': 25, 'line': 12},
                    },
                    'selectionRange': {
                        'start': {'character': 8, 'line': 11},
                        'end': {'character': 15, 'line': 11},
                    },
                },
                {
                    'detail': 'class ResponseParser',
                    'kind': 5,
                    'name': 'ResponseParser',
                    'range': {
                        'start': {'character': 0, 'line': 15},
                        'end': {'character': 12, 'line': 60},
                    },
                    'selectionRange': {
                        'start': {'character': 6, 'line': 15},
                        'end': {'character': 20, 'line': 15},
                    },
                },
                {
                    'detail': 'def __init__',
                    'kind': 6,
                    'name': '__init__',
                    'range': {
                        'start': {'character': 4, 'line': 20},
                        'end': {'character': 32, 'line': 24},
                    },
                    'selectionRange': {
                        'start': {'character': 8, 'line': 20},
                        'end': {'character': 16, 'line': 20},
                    },
                },
                {
                    'detail': 'self.action_parsers = []',
                    'kind': 7,
                    'name': 'action_parsers',
                    'range': {
                        'start': {'character': 8, 'line': 24},
                        'end': {'character': 32, 'line': 24},
                    },
                    'selectionRange': {
                        'start': {'character': 13, 'line': 24},
                        'end': {'character': 27, 'line': 24},
                    },
                },
                {
                    'detail': 'def parse',
                    'kind': 6,
                    'name': 'parse',
                    'range': {
                        'start': {'character': 4, 'line': 27},
                        'end': {'character': 12, 'line': 36},
                    },
                    'selectionRange': {
                        'start': {'character': 8, 'line': 27},
                        'end': {'character': 13, 'line': 27},
                    },
                },
                {
                    'detail': 'def parse_response',
                    'kind': 6,
                    'name': 'parse_response',
                    'range': {
                        'start': {'character': 4, 'line': 39},
                        'end': {'character': 12, 'line': 48},
                    },
                    'selectionRange': {
                        'start': {'character': 8, 'line': 39},
                        'end': {'character': 22, 'line': 39},
                    },
                },
                {
                    'detail': 'def parse_action',
                    'kind': 6,
                    'name': 'parse_action',
                    'range': {
                        'start': {'character': 4, 'line': 51},
                        'end': {'character': 12, 'line': 60},
                    },
                    'selectionRange': {
                        'start': {'character': 8, 'line': 51},
                        'end': {'character': 20, 'line': 51},
                    },
                },
                {
                    'detail': 'class ActionParser',
                    'kind': 5,
                    'name': 'ActionParser',
                    'range': {
                        'start': {'character': 0, 'line': 63},
                        'end': {'character': 12, 'line': 76},
                    },
                    'selectionRange': {
                        'start': {'character': 6, 'line': 63},
                        'end': {'character': 18, 'line': 63},
                    },
                },
                {
                    'detail': 'def check_condition',
                    'kind': 6,
                    'name': 'check_condition',
                    'range': {
                        'start': {'character': 4, 'line': 69},
                        'end': {'character': 12, 'line': 71},
                    },
                    'selectionRange': {
                        'start': {'character': 8, 'line': 69},
                        'end': {'character': 23, 'line': 69},
                    },
                },
                {
                    'detail': 'def parse',
                    'kind': 6,
                    'name': 'parse',
                    'range': {
                        'start': {'character': 4, 'line': 74},
                        'end': {'character': 12, 'line': 76},
                    },
                    'selectionRange': {
                        'start': {'character': 8, 'line': 74},
                        'end': {'character': 13, 'line': 74},
                    },
                },
            ]
