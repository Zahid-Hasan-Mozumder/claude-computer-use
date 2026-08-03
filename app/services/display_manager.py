import os
import shutil
import asyncio
import logging
from typing import Dict, Set, Optional, Any

logger = logging.getLogger("display_manager")

class DisplaySessionInfo:
    def __init__(self, display_num: int, vnc_port: int):
        self.display_num: int = display_num
        self.display_str: str = f":{display_num}"
        self.vnc_port: int = vnc_port
        self.processes: list[asyncio.subprocess.Process] = []

class DisplayManager:
    """Manages isolated virtual X11 displays (Xvfb), window managers (openbox), and VNC servers (x11vnc) per session."""

    def __init__(self, base_port: int = 5900, max_displays: int = 50):
        self.base_port = base_port
        self.max_displays = max_displays
        self._session_displays: Dict[str, DisplaySessionInfo] = {}
        self._used_display_nums: Set[int] = set()
        self._lock = asyncio.Lock()

    async def get_or_create_display(self, session_id: str) -> DisplaySessionInfo:
        """Retrieves or initializes a 100% isolated X display and VNC server for a session."""
        async with self._lock:
            if session_id in self._session_displays:
                return self._session_displays[session_id]

            # Find lowest free display number starting at 1
            display_num = 1
            while display_num in self._used_display_nums:
                display_num += 1

            if display_num > self.max_displays:
                raise RuntimeError(f"Maximum display limit ({self.max_displays}) reached.")

            # Display 1 uses base port 5900 (started by entrypoint.sh), subsequent displays use 5900 + display_num
            vnc_port = 5900 if display_num == 1 else (self.base_port + display_num)
            info = DisplaySessionInfo(display_num, vnc_port)

            # Check if X server socket for this display number is already active
            x_socket = f"/tmp/.X11-unix/X{display_num}"
            is_already_running = os.path.exists(x_socket)

            # Check if running in Linux container with Xvfb & x11vnc available
            if shutil.which("Xvfb") and shutil.which("x11vnc") and not is_already_running:
                env = os.environ.copy()
                env["DISPLAY"] = info.display_str

                try:
                    # 1. Start Xvfb virtual framebuffer
                    logger.info(f"Starting Xvfb on display {info.display_str} for session {session_id}...")
                    xvfb_proc = await asyncio.create_subprocess_shell(
                        f"Xvfb {info.display_str} -screen 0 1024x768x24",
                        env=env
                    )
                    info.processes.append(xvfb_proc)
                    await asyncio.sleep(0.5)

                    # 2. Start Openbox Window Manager
                    if shutil.which("openbox"):
                        openbox_proc = await asyncio.create_subprocess_shell(
                            "openbox",
                            env=env
                        )
                        info.processes.append(openbox_proc)

                    # 3. Set dark background color to prevent pitch-black VNC screen
                    if shutil.which("xsetroot"):
                        await asyncio.create_subprocess_shell(
                            "xsetroot -solid '#1e1e2e'",
                            env=env
                        )

                    # 4. Start Desktop panel if present
                    if shutil.which("tint2"):
                        tint2_proc = await asyncio.create_subprocess_shell(
                            "tint2",
                            env=env
                        )
                        info.processes.append(tint2_proc)

                    # 5. Start x11vnc VNC Server on assigned RFB port
                    logger.info(f"Starting x11vnc on port {vnc_port} for display {info.display_str}...")
                    vnc_proc = await asyncio.create_subprocess_shell(
                        f"x11vnc -display {info.display_str} -forever -shared -rfbport {vnc_port} -nopw",
                        env=env
                    )
                    info.processes.append(vnc_proc)
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error(f"Failed to launch X11/VNC display for session {session_id}: {str(e)}")

            self._used_display_nums.add(display_num)
            self._session_displays[session_id] = info
            return info

    async def release_display(self, session_id: str):
        """Terminates display processes, removes temp profile dirs, and frees display number for reuse."""
        async with self._lock:
            info = self._session_displays.pop(session_id, None)
            if not info:
                return

            self._used_display_nums.discard(info.display_num)

            for proc in info.processes:
                try:
                    proc.terminate()
                    await asyncio.sleep(0.1)
                    if proc.returncode is None:
                        proc.kill()
                except Exception as e:
                    logger.warning(f"Error terminating process for session {session_id}: {str(e)}")

            profile_dir = f"/tmp/firefox_profiles/{session_id}"
            if os.path.exists(profile_dir):
                try:
                    shutil.rmtree(profile_dir, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"Failed to remove profile dir for session {session_id}: {e}")

            logger.info(f"Released display {info.display_str} for session {session_id}")

    async def cleanup_all(self):
        """Cleanly terminates all active display processes across sessions."""
        async with self._lock:
            for session_id, info in list(self._session_displays.items()):
                for proc in info.processes:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            self._session_displays.clear()
            self._used_display_nums.clear()

display_manager = DisplayManager()
