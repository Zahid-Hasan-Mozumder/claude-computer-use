from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass
from anthropic.types.beta import BetaToolUnionParam

@dataclass(frozen=True)
class CLIResult:
    """Result of a CLI command execution."""
    output: Optional[str] = None
    error: Optional[str] = None
    base64_image: Optional[str] = None
    system: Optional[str] = None

class ToolError(Exception):
    """Exception raised by tools when execution fails."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

@dataclass(frozen=True)
class ToolResult:
    """Result of a tool execution formatted for Anthropic API."""
    output: Optional[str] = None
    error: Optional[str] = None
    base64_image: Optional[str] = None
    system: Optional[str] = None

    def __bool__(self):
        return any(v is not None for v in (self.output, self.error, self.base64_image, self.system))

    def to_content_blocks(self) -> list[Dict[str, Any]]:
        """Converts ToolResult into content blocks format expected by Anthropic messages API."""
        blocks = []
        if self.error:
            blocks.append({"type": "text", "text": f"Error: {self.error}"})
        elif self.output:
            blocks.append({"type": "text", "text": self.output})

        if self.base64_image:
            blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": self.base64_image,
                }
            })
        return blocks

class BaseAnthropicTool(ABC):
    """Abstract base class for Anthropic Computer Use tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the tool."""
        pass

    @abstractmethod
    def to_params(self) -> BetaToolUnionParam:
        """Returns tool schema param for Anthropic API."""
        pass

    @abstractmethod
    async def __call__(self, **kwargs) -> ToolResult:
        """Executes the tool with given keyword arguments asynchronously."""
        pass
