import json
import uuid

from openhands_aci.core.results import ToolResult, make_api_tool_result

from .editor import Command, OHEditor
from .exceptions import ToolError

_GLOBAL_EDITOR = OHEditor()


def file_editor(
    command: Command,
    path: str,
    file_text: str | None = None,
    view_range: list[int] | None = None,
    old_str: str | None = None,
    new_str: str | None = None,
    insert_line: int | None = None,
    enable_linting: bool = False,
) -> str:
    result: ToolResult | None = None
    try:
        result = _GLOBAL_EDITOR(
            command=command,
            path=path,
            file_text=file_text,
            view_range=view_range,
            old_str=old_str,
            new_str=new_str,
            insert_line=insert_line,
            enable_linting=enable_linting,
        )
    except ToolError as e:
        result = ToolResult(error=e.message)

    formatted_output_and_error = make_api_tool_result(result)
    marker_id = uuid.uuid4().hex
    return f"""<oh_aci_output_{marker_id}>
{json.dumps(result.to_dict(extra_field={'formatted_output_and_error': formatted_output_and_error}), indent=2)}
</oh_aci_output_{marker_id}>"""
