from openhands_aci.core.exceptions import ToolError
from openhands_aci.core.results import ToolResult, make_api_tool_result

from .navigator import Command, SymbolNavigator

_GLOBAL_NAVIGATOR = SymbolNavigator()


def symbol_navigator(
    command: Command,
    symbol_name: str,
) -> str:
    result: ToolResult | None = None
    try:
        result = _GLOBAL_NAVIGATOR(
            command=command,
            symbol_name=symbol_name,
        )
    except ToolError as e:
        result = ToolResult(error=e.message)

    return make_api_tool_result(result)  # Return as default IPython output
