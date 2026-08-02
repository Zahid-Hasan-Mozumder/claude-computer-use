from typing import Any, Dict, List
from anthropic.types.beta import BetaToolUnionParam
from app.agent.tools.base import BaseAnthropicTool, ToolResult, ToolError
from app.agent.tools.computer import ComputerTool
from app.agent.tools.bash import BashTool
from app.agent.tools.edit import EditTool

class ToolCollection:
    """Collection of tools available to the Anthropic computer use agent."""

    def __init__(self, tools: List[BaseAnthropicTool] = None):
        if tools is None:
            tools = [ComputerTool(), BashTool(), EditTool()]
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
