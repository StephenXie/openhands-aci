import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Literal, get_args

from binaryornot.check import is_binary

from openhands_aci.linter import DefaultLinter
from openhands_aci.utils.shell import run_shell_cmd

from .config import SNIPPET_CONTEXT_WINDOW
from .exceptions import (
    EditorToolParameterInvalidError,
    EditorToolParameterMissingError,
    FileValidationError,
    ToolError,
)
from .history import FileHistoryManager
from .prompts import DIRECTORY_CONTENT_TRUNCATED_NOTICE, FILE_CONTENT_TRUNCATED_NOTICE
from .results import CLIResult, maybe_truncate

Command = Literal[
    'view',
    'create',
    'str_replace',
    'insert',
    'undo_edit',
    # 'jump_to_definition', TODO:
    # 'find_references' TODO:
]


class OHEditor:
    """
    An filesystem editor tool that allows the agent to
    - view
    - create
    - navigate
    - edit files
    The tool parameters are defined by Anthropic and are not editable.

    Original implementation: https://github.com/anthropics/anthropic-quickstarts/blob/main/computer-use-demo/computer_use_demo/tools/edit.py
    """

    TOOL_NAME = 'oh_editor'
    MAX_FILE_SIZE_MB = 10  # Maximum file size in MB

    def __init__(
        self,
        max_file_size_mb: int | None = None,
        workspace_root: str | None = None,
    ):
        """Initialize the editor.

        Args:
            max_file_size_mb: Maximum file size in MB. If None, uses the default MAX_FILE_SIZE_MB.
            workspace_root: Root directory that restricts file access and serves as the current working directory
                           for relative path suggestions. If None, no path restriction is applied and the current
                           working directory is used for relative path suggestions.
        """
        self._linter = DefaultLinter()
        self._history_manager = FileHistoryManager(max_history_per_file=10)
        self._max_file_size = (
            (max_file_size_mb or self.MAX_FILE_SIZE_MB) * 1024 * 1024
        )  # Convert to bytes
        self._workspace_root = (
            Path(workspace_root) if workspace_root is not None else None
        )
        # Use workspace_root as cwd if provided, otherwise use current working directory
        self._cwd = (
            str(self._workspace_root)
            if self._workspace_root is not None
            else os.getcwd()
        )

    def __call__(
        self,
        *,
        command: Command,
        path: str,
        file_text: str | None = None,
        view_range: list[int] | None = None,
        old_str: str | None = None,
        new_str: str | None = None,
        insert_line: int | None = None,
        enable_linting: bool = False,
        **kwargs,
    ) -> CLIResult:
        _path = Path(path)
        self.validate_path(command, _path)
        if command == 'view':
            return self.view(_path, view_range)
        elif command == 'create':
            if file_text is None:
                raise EditorToolParameterMissingError(command, 'file_text')
            self.write_file(_path, file_text)
            self._history_manager.add_history(_path, file_text)
            return CLIResult(
                path=str(_path),
                new_content=file_text,
                prev_exist=False,
                output=f'File created successfully at: {_path}',
            )
        elif command == 'str_replace':
            if old_str is None:
                raise EditorToolParameterMissingError(command, 'old_str')
            if new_str == old_str:
                raise EditorToolParameterInvalidError(
                    'new_str',
                    new_str,
                    'No replacement was performed. `new_str` and `old_str` must be different.',
                )
            return self.str_replace(_path, old_str, new_str, enable_linting)
        elif command == 'insert':
            if insert_line is None:
                raise EditorToolParameterMissingError(command, 'insert_line')
            if new_str is None:
                raise EditorToolParameterMissingError(command, 'new_str')
            return self.insert(_path, insert_line, new_str, enable_linting)
        elif command == 'undo_edit':
            return self.undo_edit(_path)

        raise ToolError(
            f'Unrecognized command {command}. The allowed commands for the {self.TOOL_NAME} tool are: {", ".join(get_args(Command))}'
        )

    def _count_lines(self, path: Path) -> int:
        """
        Count the number of lines in a file safely.
        """
        with open(path) as f:
            return sum(1 for _ in f)

    def str_replace(
        self, path: Path, old_str: str, new_str: str | None, enable_linting: bool
    ) -> CLIResult:
        """
        Implement the str_replace command, which replaces old_str with new_str in the file content.
        """
        self.validate_file(path)
        old_str = old_str.expandtabs()
        new_str = new_str.expandtabs() if new_str is not None else ''

        # Read the entire file first to handle both single-line and multi-line replacements
        file_content = self.read_file(path).expandtabs()

        # Find all occurrences using regex
        # Escape special regex characters in old_str to match it literally
        pattern = re.escape(old_str)
        occurrences = [
            (
                file_content.count('\n', 0, match.start()) + 1,  # line number
                match.group(),  # matched text
                match.start(),  # start position
            )
            for match in re.finditer(pattern, file_content)
        ]

        if not occurrences:
            raise ToolError(
                f'No replacement was performed, old_str `{old_str}` did not appear verbatim in {path}.'
            )
        if len(occurrences) > 1:
            line_numbers = sorted(set(line for line, _, _ in occurrences))
            raise ToolError(
                f'No replacement was performed. Multiple occurrences of old_str `{old_str}` in lines {line_numbers}. Please ensure it is unique.'
            )

        # We found exactly one occurrence
        replacement_line, matched_text, idx = occurrences[0]

        # Create new content by replacing just the matched text
        new_file_content = (
            file_content[:idx] + new_str + file_content[idx + len(matched_text) :]
        )

        # Write the new content to the file
        self.write_file(path, new_file_content)

        # Save the content to history
        self._history_manager.add_history(path, file_content)

        # Create a snippet of the edited section
        start_line = max(0, replacement_line - SNIPPET_CONTEXT_WINDOW)
        end_line = replacement_line + SNIPPET_CONTEXT_WINDOW + new_str.count('\n')

        # Read just the snippet range
        snippet = self.read_file(path, start_line=start_line, end_line=end_line)

        # Prepare the success message
        success_message = f'The file {path} has been edited. '
        success_message += self._make_output(
            snippet, f'a snippet of {path}', start_line + 1
        )

        if enable_linting:
            # Run linting on the changes
            lint_results = self._run_linting(file_content, new_file_content, path)
            success_message += '\n' + lint_results + '\n'

        success_message += 'Review the changes and make sure they are as expected. Edit the file again if necessary.'
        return CLIResult(
            output=success_message,
            prev_exist=True,
            path=str(path),
            old_content=file_content,
            new_content=new_file_content,
        )

    def view(self, path: Path, view_range: list[int] | None = None) -> CLIResult:
        """
        View the contents of a file or a directory.
        """
        if path.is_dir():
            if view_range:
                raise EditorToolParameterInvalidError(
                    'view_range',
                    view_range,
                    'The `view_range` parameter is not allowed when `path` points to a directory.',
                )

            # First count hidden files/dirs in current directory only
            # -mindepth 1 excludes . and .. automatically
            _, hidden_stdout, _ = run_shell_cmd(
                rf"find -L {path} -mindepth 1 -maxdepth 1 -name '.*'"
            )
            hidden_count = (
                len(hidden_stdout.strip().split('\n')) if hidden_stdout.strip() else 0
            )

            # Then get files/dirs up to 2 levels deep, excluding hidden entries at both depth 1 and 2
            _, stdout, stderr = run_shell_cmd(
                rf"find -L {path} -maxdepth 2 -not \( -path '{path}/\.*' -o -path '{path}/*/\.*' \) | sort",
                truncate_notice=DIRECTORY_CONTENT_TRUNCATED_NOTICE,
            )
            if not stderr:
                # Add trailing slashes to directories
                paths = stdout.strip().split('\n') if stdout.strip() else []
                formatted_paths = []
                for p in paths:
                    if Path(p).is_dir():
                        formatted_paths.append(f'{p}/')
                    else:
                        formatted_paths.append(p)

                msg = [
                    f"Here's the files and directories up to 2 levels deep in {path}, excluding hidden items:\n"
                    + '\n'.join(formatted_paths)
                ]
                if hidden_count > 0:
                    msg.append(
                        f"\n{hidden_count} hidden files/directories in this directory are excluded. You can use 'ls -la {path}' to see them."
                    )
                stdout = '\n'.join(msg)
            return CLIResult(
                output=stdout,
                error=stderr,
                path=str(path),
                prev_exist=True,
            )

        # Validate file and count lines
        self.validate_file(path)
        num_lines = self._count_lines(path)

        start_line = 1
        if not view_range:
            file_content = self.read_file(path)
            return CLIResult(
                output=self._make_output(file_content, str(path), start_line),
                path=str(path),
                prev_exist=True,
            )

        if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
            raise EditorToolParameterInvalidError(
                'view_range',
                view_range,
                'It should be a list of two integers.',
            )

        start_line, end_line = view_range
        if start_line < 1 or start_line > num_lines:
            raise EditorToolParameterInvalidError(
                'view_range',
                view_range,
                f'Its first element `{start_line}` should be within the range of lines of the file: {[1, num_lines]}.',
            )

        if end_line > num_lines:
            raise EditorToolParameterInvalidError(
                'view_range',
                view_range,
                f'Its second element `{end_line}` should be smaller than the number of lines in the file: `{num_lines}`.',
            )

        if end_line != -1 and end_line < start_line:
            raise EditorToolParameterInvalidError(
                'view_range',
                view_range,
                f'Its second element `{end_line}` should be greater than or equal to the first element `{start_line}`.',
            )

        if end_line == -1:
            end_line = num_lines

        file_content = self.read_file(path, start_line=start_line, end_line=end_line)
        return CLIResult(
            path=str(path),
            output=self._make_output(file_content, str(path), start_line),
            prev_exist=True,
        )

    def write_file(self, path: Path, file_text: str) -> None:
        """
        Write the content of a file to a given path; raise a ToolError if an error occurs.
        """
        self.validate_file(path)
        try:
            path.write_text(file_text)
        except Exception as e:
            raise ToolError(f'Ran into {e} while trying to write to {path}') from None

    def insert(
        self, path: Path, insert_line: int, new_str: str, enable_linting: bool
    ) -> CLIResult:
        """
        Implement the insert command, which inserts new_str at the specified line in the file content.
        """
        # Validate file and count lines
        self.validate_file(path)
        num_lines = self._count_lines(path)

        if insert_line < 0 or insert_line > num_lines:
            raise EditorToolParameterInvalidError(
                'insert_line',
                insert_line,
                f'It should be within the range of lines of the file: {[0, num_lines]}',
            )

        new_str = new_str.expandtabs()
        new_str_lines = new_str.split('\n')

        # Create temporary file for the new content
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            # Copy lines before insert point and save them for history
            history_lines = []
            with open(path, 'r') as f:
                for i, line in enumerate(f, 1):
                    if i > insert_line:
                        break
                    temp_file.write(line.expandtabs())
                    history_lines.append(line)

            # Insert new content
            for line in new_str_lines:
                temp_file.write(line + '\n')

            # Copy remaining lines and save them for history
            with open(path, 'r') as f:
                for i, line in enumerate(f, 1):
                    if i <= insert_line:
                        continue
                    temp_file.write(line.expandtabs())
                    history_lines.append(line)

        # Move temporary file to original location
        shutil.move(temp_file.name, path)

        # Read just the snippet range
        start_line = max(1, insert_line - SNIPPET_CONTEXT_WINDOW)
        end_line = min(
            num_lines + len(new_str_lines),
            insert_line + SNIPPET_CONTEXT_WINDOW + len(new_str_lines),
        )
        snippet = self.read_file(path, start_line=start_line, end_line=end_line)

        # Save history - we already have the lines in memory
        file_text = ''.join(history_lines)
        self._history_manager.add_history(path, file_text)

        # Read new content for result
        new_file_text = self.read_file(path)

        success_message = f'The file {path} has been edited. '
        success_message += self._make_output(
            snippet,
            'a snippet of the edited file',
            max(1, insert_line - SNIPPET_CONTEXT_WINDOW + 1),
        )

        if enable_linting:
            # Run linting on the changes
            lint_results = self._run_linting(file_text, new_file_text, path)
            success_message += '\n' + lint_results + '\n'

        success_message += 'Review the changes and make sure they are as expected (correct indentation, no duplicate lines, etc). Edit the file again if necessary.'
        return CLIResult(
            output=success_message,
            prev_exist=True,
            path=str(path),
            old_content=file_text,
            new_content=new_file_text,
        )

    def validate_path(self, command: Command, path: Path) -> None:
        """
        Check that the path/command combination is valid.

        Validates:
        1. Path is absolute
        2. Path is within workspace_root (if specified)
        3. Path and command are compatible
        """
        # Check if its an absolute path
        if not path.is_absolute():
            suggested_path = Path(self._cwd) / path
            raise EditorToolParameterInvalidError(
                'path',
                path,
                f'The path should be an absolute path, starting with `/`. Maybe you meant {suggested_path}?',
            )

        # Check if path is within workspace_root (if specified)
        if self._workspace_root is not None:
            try:
                # Resolve to absolute path to handle symlinks and normalize path
                abs_path = path.resolve()
                if not abs_path.is_relative_to(self._workspace_root):
                    raise EditorToolParameterInvalidError(
                        'path',
                        path,
                        f'File access not permitted: {path}. You can only access paths inside the workspace.',
                    )
            except (ValueError, RuntimeError):
                # ValueError can be raised by is_relative_to in some edge cases
                # RuntimeError can be raised by resolve() if path doesn't exist
                raise EditorToolParameterInvalidError(
                    'path',
                    path,
                    f'File access not permitted: {path}. You can only access paths inside the workspace.',
                )

        # Check if path and command are compatible
        if command == 'create' and path.exists():
            raise EditorToolParameterInvalidError(
                'path',
                path,
                f'File already exists at: {path}. Cannot overwrite files using command `create`.',
            )
        if command != 'create' and not path.exists():
            raise EditorToolParameterInvalidError(
                'path',
                path,
                f'The path {path} does not exist. Please provide a valid path.',
            )
        if command != 'view' and path.is_dir():
            raise EditorToolParameterInvalidError(
                'path',
                path,
                f'The path {path} is a directory and only the `view` command can be used on directories.',
            )

    def undo_edit(self, path: Path) -> CLIResult:
        """
        Implement the undo_edit command.
        """
        current_text = self.read_file(path).expandtabs()
        old_text = self._history_manager.pop_last_history(path)
        if old_text is None:
            raise ToolError(f'No edit history found for {path}.')

        self.write_file(path, old_text)

        return CLIResult(
            output=f'Last edit to {path} undone successfully. {self._make_output(old_text, str(path))}',
            path=str(path),
            prev_exist=True,
            old_content=current_text,
            new_content=old_text,
        )

    def validate_file(self, path: Path) -> None:
        """
        Validate a file for reading or editing operations.

        Args:
            path: Path to the file to validate

        Raises:
            FileValidationError: If the file fails validation
        """
        if not path.is_file():
            return  # Skip validation for directories

        # Check file size
        file_size = os.path.getsize(path)
        max_size = self._max_file_size
        if file_size > max_size:
            raise FileValidationError(
                path=str(path),
                reason=f'File is too large ({file_size / 1024 / 1024:.1f}MB). Maximum allowed size is {int(max_size / 1024 / 1024)}MB.',
            )

        # Check file type
        if is_binary(str(path)):
            raise FileValidationError(
                path=str(path),
                reason='File appears to be binary. Only text files can be edited.',
            )

    def read_file(
        self,
        path: Path,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        """
        Read the content of a file from a given path; raise a ToolError if an error occurs.

        Args:
            path: Path to the file to read
            start_line: Optional start line number (1-based). If provided with end_line, only reads that range.
            end_line: Optional end line number (1-based). Must be provided with start_line.
        """
        self.validate_file(path)
        try:
            if start_line is not None and end_line is not None:
                # Read only the specified line range
                lines = []
                with open(path, 'r') as f:
                    for i, line in enumerate(f, 1):
                        if i > end_line:
                            break
                        if i >= start_line:
                            lines.append(line)
                return ''.join(lines)
            elif start_line is not None or end_line is not None:
                raise ValueError(
                    'Both start_line and end_line must be provided together'
                )
            else:
                # Use line-by-line reading to avoid loading entire file into memory
                with open(path, 'r') as f:
                    return ''.join(f)
        except Exception as e:
            raise ToolError(f'Ran into {e} while trying to read {path}') from None

    def _make_output(
        self,
        snippet_content: str,
        snippet_description: str,
        start_line: int = 1,
        expand_tabs: bool = True,
    ) -> str:
        """
        Generate output for the CLI based on the content of a code snippet.
        """
        snippet_content = maybe_truncate(
            snippet_content, truncate_notice=FILE_CONTENT_TRUNCATED_NOTICE
        )
        if expand_tabs:
            snippet_content = snippet_content.expandtabs()

        snippet_content = '\n'.join(
            [
                f'{i + start_line:6}\t{line}'
                for i, line in enumerate(snippet_content.split('\n'))
            ]
        )
        return (
            f"Here's the result of running `cat -n` on {snippet_description}:\n"
            + snippet_content
            + '\n'
        )

    def _run_linting(self, old_content: str, new_content: str, path: Path) -> str:
        """
        Run linting on file changes and return formatted results.
        """
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create paths with exact filenames in temp directory
            temp_old = Path(temp_dir) / f'old.{path.name}'
            temp_new = Path(temp_dir) / f'new.{path.name}'

            # Write content to temporary files
            temp_old.write_text(old_content)
            temp_new.write_text(new_content)

            # Run linting on the changes
            results = self._linter.lint_file_diff(str(temp_old), str(temp_new))

            if not results:
                return 'No linting issues found in the changes.'

            # Format results
            output = ['Linting issues found in the changes:']
            for result in results:
                output.append(
                    f'- Line {result.line}, Column {result.column}: {result.message}'
                )
            return '\n'.join(output) + '\n'
