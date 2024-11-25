import os
from typing import Literal

from openhands_aci.exceptions import ToolError
from openhands_aci.results import ToolResult

from .typing import ScalingSource

Action = Literal[
    'type',  # type sequence in chunks           --> keyboard_type
    'key',  # key sequence pressed               --> keyboard_type
    'mouse_move',  # move mouse to a position    --> mouse_move
    'left_click',  # left click                  --> mouse_click
    'left_click_drag',  # left click and drag    --> mouse_drag_and_drop
    'right_click',  # right click                --> mouse_click
    'middle_click',  # middle click              --> mouse_click
    'double_click',  # double left click         --> mouse_dblclick
    'screenshot',  # take a screenshot           -->
    'cursor_position',  # get cursor position    -->
]


class GUIUseTool:
    """
    A tool that allows the agent to interact with the screen, keyboard, and mouse of the current computer.
    The tool parameters are defined by Anthropic and are not editable.

    Original implementation: https://github.com/anthropics/anthropic-quickstarts/blob/main/computer-use-demo/computer_use_demo/tools/computer.py
    """

    TOOL_NAME = 'gui_use'

    width: int
    height: int
    display_num: int | None

    def __init__(self):
        self.width = int(os.getenv('WIDTH') or 0)  # Screen width
        self.height = int(os.getenv('HEIGHT') or 0)
        assert self.width and self.height, 'WIDTH, HEIGHT must be set'

        if (display_num := os.getenv('DISPLAY_NUM')) is not None:
            self.display_num = int(display_num)
            self._display_prefix = f'DISPLAY=:{self.display_num} '
        else:
            self.display_num = None
            self._display_prefix = ''

        self.xdotool = f'{self._display_prefix}xdotool'

    def __call__(
        self,
        *,
        action: Action,
        text: str | None = None,
        coordinate: tuple[int, int] | None = None,
        **kwargs,
    ):
        if action in ('mouse_move', 'left_click_drag'):
            if coordinate is None:
                raise ToolError(f'coordinate is required for {action}')
            if text is not None:
                raise ToolError(f'text is not accepted for {action}')
            if not isinstance(coordinate, tuple) or len(coordinate) != 2:
                raise ToolError(f'{coordinate} must be a tuple of length 2')
            if not all(isinstance(i, int) and i >= 0 for i in coordinate):
                raise ToolError(f'{coordinate} must be a tuple of non-negative ints')

            x, y = self.scale_coordinates(
                ScalingSource.API, coordinate[0], coordinate[1]
            )

            if action == 'mouse_move':
                return self.shell(f'{self.xdotool} mousemove --sync {x} {y}')
            elif action == 'left_click_drag':
                return self.shell(
                    f'{self.xdotool} mousedown 1 mousemove --sync {x} {y} mouseup 1'
                )

        # TODO: Implement other actions

    def scale_coordinates(
        self, source: ScalingSource, x: int, y: int
    ) -> tuple[int, int]:
        # TODO:
        raise NotImplementedError

    def shell(self, command: str, take_screenshot=True) -> ToolResult:
        # TODO:
        raise NotImplementedError
