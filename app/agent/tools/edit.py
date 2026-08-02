import os
from typing import Any, Dict, Optional
from anthropic.types.beta import BetaToolUnionParam
from app.agent.tools.base import BaseAnthropicTool, ToolResult

class EditTool(BaseAnthropicTool):
    """Tool for viewing and editing text files."""

    def __init__(self):
        self._history: Dict[str, list[str]] = {}

    @property
    def name(self) -> str:
        return "str_replace_editor"

    def to_params(self) -> BetaToolUnionParam:
        return {
            "name": self.name,
            "description": "Custom text editor tool to view, create, and edit files.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "enum": ["view", "create", "str_replace", "insert", "undo_edit"],
                        "description": "The editing command to perform."
                    },
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the target file or directory."
                    },
                    "file_text": {
                        "type": "string",
                        "description": "Content for creating a new file."
                    },
                    "old_str": {
                        "type": "string",
                        "description": "String to be replaced."
                    },
                    "new_str": {
                        "type": "string",
                        "description": "String to replace old_str with."
                    },
                    "insert_line": {
                        "type": "integer",
                        "description": "Line number after which new_str will be inserted."
                    },
                    "view_range": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Start and end line range to view [start, end]."
                    }
                },
                "required": ["command", "path"]
            }
        }

    async def __call__(
        self,
        command: str,
        path: str,
        file_text: Optional[str] = None,
        old_str: Optional[str] = None,
        new_str: Optional[str] = None,
        insert_line: Optional[int] = None,
        view_range: Optional[list[int]] = None,
        **kwargs: Any
    ) -> ToolResult:
        try:
            if command == "view":
                return self._view(path, view_range)
            elif command == "create":
                return self._create(path, file_text or "")
            elif command == "str_replace":
                return self._str_replace(path, old_str or "", new_str or "")
            elif command == "insert":
                return self._insert(path, insert_line or 0, new_str or "")
            elif command == "undo_edit":
                return self._undo_edit(path)
            else:
                return ToolResult(error=f"Unknown command: {command}")
        except Exception as e:
            return ToolResult(error=f"Error executing editor command '{command}': {str(e)}")

    def _view(self, path: str, view_range: Optional[list[int]]) -> ToolResult:
        if os.path.isdir(path):
            files = os.listdir(path)
            return ToolResult(output=f"Directory listing for {path}:\n" + "\n".join(files))
        
        if not os.path.exists(path):
            return ToolResult(error=f"File not found: {path}")

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if view_range and len(view_range) == 2:
            start, end = max(1, view_range[0]), view_range[1]
            lines = lines[start - 1 : end]

        formatted = "".join([f"{i+1:6d} | {line}" for i, line in enumerate(lines)])
        return ToolResult(output=formatted)

    def _create(self, path: str, file_text: str) -> ToolResult:
        if os.path.exists(path):
            return ToolResult(error=f"File already exists at path: {path}")
        
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(file_text)
        return ToolResult(output=f"File created successfully at {path}")

    def _str_replace(self, path: str, old_str: str, new_str: str) -> ToolResult:
        if not os.path.exists(path):
            return ToolResult(error=f"File not found: {path}")
        
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if old_str not in content:
            return ToolResult(error=f"Target string '{old_str}' not found in {path}")

        if path not in self._history:
            self._history[path] = []
        self._history[path].append(content)

        new_content = content.replace(old_str, new_str)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return ToolResult(output=f"Successfully replaced text in {path}")

    def _insert(self, path: str, insert_line: int, new_str: str) -> ToolResult:
        if not os.path.exists(path):
            return ToolResult(error=f"File not found: {path}")

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if path not in self._history:
            self._history[path] = []
        self._history[path].append("".join(lines))

        insert_idx = max(0, min(insert_line, len(lines)))
        lines.insert(insert_idx, new_str + "\n")

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return ToolResult(output=f"Inserted line into {path} at line {insert_idx+1}")

    def _undo_edit(self, path: str) -> ToolResult:
        if path not in self._history or not self._history[path]:
            return ToolResult(error=f"No edit history found for {path}")
        
        previous_content = self._history[path].pop()
        with open(path, "w", encoding="utf-8") as f:
            f.write(previous_content)
        return ToolResult(output=f"Reverted last edit for {path}")
