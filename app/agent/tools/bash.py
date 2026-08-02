import os
import sys
import asyncio
from typing import Any
from anthropic.types.beta import BetaToolUnionParam
from app.agent.tools.base import BaseAnthropicTool, ToolResult

class BashTool(BaseAnthropicTool):
    """Tool for executing shell commands cross-platform."""

    @property
    def name(self) -> str:
        return "bash"

    def to_params(self) -> BetaToolUnionParam:
        return {
            "name": self.name,
            "description": "Run a bash shell command and return its stdout/stderr output.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute."
                    }
                },
                "required": ["command"]
            }
        }

    async def __call__(self, command: str = "", **kwargs: Any) -> ToolResult:
        if not command:
            return ToolResult(error="No command provided.")

        try:
            # On Windows, if command starts with echo '...', clean up quotes or run via cmd/powershell
            exec_cmd = command
            if sys.platform == "win32" and not (command.startswith("cmd") or command.startswith("powershell")):
                # Replace bash single quotes for echo on Windows shell if needed
                pass

            process = await asyncio.create_subprocess_shell(
                exec_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(error="Command execution timed out after 30 seconds.")

            out_str = stdout.decode("utf-8", errors="replace").strip()
            err_str = stderr.decode("utf-8", errors="replace").strip()

            combined = []
            if out_str:
                combined.append(out_str)
            if err_str:
                combined.append(f"[stderr]\n{err_str}")

            output_text = "\n".join(combined) if combined else "Command executed with no output."
            
            if process.returncode != 0:
                return ToolResult(error=f"Exit code {process.returncode}:\n{output_text}")
            
            return ToolResult(output=output_text)

        except Exception as e:
            return ToolResult(error=f"Failed to execute command: {str(e)}")
