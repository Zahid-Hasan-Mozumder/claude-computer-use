import os
import sys
import shutil
import asyncio
import re
from typing import Any, Optional
from anthropic.types.beta import BetaToolUnionParam
from app.agent.tools.base import BaseAnthropicTool, ToolResult
from app.core.config import settings

class BashTool(BaseAnthropicTool):
    """Tool for executing shell commands cross-platform."""

    def __init__(self, display: Optional[str] = None, session_id: Optional[str] = None):
        self.display = display or settings.DISPLAY
        self.session_id = session_id or "default"

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
            exec_cmd = command
            # Dynamically rewrite any explicit DISPLAY assignments (e.g., DISPLAY=:1 or export DISPLAY=:1)
            # to match this session's isolated display.
            if self.display:
                exec_cmd = re.sub(r'\bDISPLAY=:\d+\b', f'DISPLAY={self.display}', exec_cmd)

            # Check if command is a utility command (grep, apt, dpkg, which, find, ls, echo, cat, ps)
            is_utility_cmd = any(u in exec_cmd for u in ["grep", "apt", "dpkg", "which", "find", "ls", "echo", "cat", "ps"])

            if not is_utility_cmd:
                # Automatically resolve web browser commands to firefox-esr
                browser_commands = ["google-chrome", "chromium-browser", "chromium", "x-www-browser", "web-browser"]
                for b_cmd in browser_commands:
                    if b_cmd in exec_cmd and "firefox" not in exec_cmd:
                        exec_cmd = exec_cmd.replace(b_cmd, "firefox-esr")

                # Inject session-isolated profile for Firefox only when launching Firefox
                if ("firefox" in exec_cmd or "firefox-esr" in exec_cmd) and "--profile" not in exec_cmd:
                    profile_dir = f"/tmp/firefox_profiles/{self.session_id}"
                    os.makedirs(profile_dir, exist_ok=True)
                    ff_args = f"--new-instance --profile {profile_dir}"
                    exec_cmd = re.sub(r'\b(firefox-esr|firefox)\b', r'\1 ' + ff_args, exec_cmd, count=1)

            env = os.environ.copy()
            env["DISPLAY"] = self.display

            # If command launches a background process (ends with & or runs GUI apps like firefox),
            # redirect output to /dev/null so process.communicate() doesn't hang on open pipes.
            is_bg = exec_cmd.strip().endswith("&") or (
                not is_utility_cmd and any(app in exec_cmd for app in ["firefox", "firefox-esr", "xterm", "openbox"])
            )
            if is_bg and ">/dev/null" not in exec_cmd and "> /dev/null" not in exec_cmd:
                clean_cmd = exec_cmd.strip()
                if clean_cmd.endswith("&"):
                    clean_cmd = clean_cmd[:-1].strip()
                exec_cmd = f"{clean_cmd} > /dev/null 2>&1 &"

            process = await asyncio.create_subprocess_shell(
                exec_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
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
