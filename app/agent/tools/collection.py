from typing import Any, Dict, List, Optional
from anthropic.types.beta import BetaToolUnionParam
from app.agent.tools.base import BaseAnthropicTool, ToolResult, ToolError
from app.agent.tools.computer import ComputerTool
from app.agent.tools.bash import BashTool
from app.agent.tools.edit import EditTool

class ToolCollection:
    """Collection of tools available to the Anthropic computer use agent."""

    def __init__(self, tools: List[BaseAnthropicTool] = None, display: Optional[str] = None, session_id: Optional[str] = None):
        if tools is None:
            tools = [ComputerTool(display=display), BashTool(display=display, session_id=session_id), EditTool()]
        self.tools_map: Dict[str, BaseAnthropicTool] = {tool.name: tool for tool in tools}

    def to_params(self) -> List[BetaToolUnionParam]:
        """Returns list of tool parameters for the Anthropic messages API."""
        return [tool.to_params() for tool in self.tools_map.values()]

    async def run(self, name: str, tool_input: Dict[str, Any]) -> ToolResult:
        """Finds tool by name and executes it with given input parameters."""
        tool = self.tools_map.get(name)
        if not tool:
            return ToolResult(error=f"Tool '{name}' not found.")

        try:
            return await tool(**tool_input)
        except ToolError as e:
            return ToolResult(error=e.message)
        except Exception as e:
            return ToolResult(error=f"Unexpected error executing tool '{name}': {str(e)}")
