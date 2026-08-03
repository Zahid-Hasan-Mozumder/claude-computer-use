import asyncio
import logging
from typing import Dict, Set, Optional, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agent.loop import sampling_loop
from app.db.database import AsyncSessionLocal
from app.db.models import SessionModel, MessageModel
from app.services.display_manager import display_manager

logger = logging.getLogger("session_manager")

class SessionState:
    """Holds runtime state, concurrency locks, and WebSocket subscribers for a single session."""
    def __init__(self, session_id: str):
        self.session_id: str = session_id
        self.status: str = "idle"
        self.lock: asyncio.Lock = asyncio.Lock()
        self.subscribers: Set[asyncio.Queue] = set()
        self.current_task: Optional[asyncio.Task] = None

class SessionManager:
    """Thread-safe and async-safe session manager ensuring race-condition-free agent execution."""

    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._global_lock: asyncio.Lock = asyncio.Lock()

    async def get_session_workspace(self, session_id: str) -> str:
        """Returns and ensures creation of the session workspace directory."""
        import tempfile
        import os
        workspace_dir = os.path.join(tempfile.gettempdir(), "session_workspaces", session_id)
        os.makedirs(workspace_dir, exist_ok=True)
        return workspace_dir

    async def get_session_state(self, session_id: str) -> SessionState:
        """Retrieves or creates in-memory session runtime state atomically."""
        async with self._global_lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionState(session_id)
            return self._sessions[session_id]

    async def subscribe(self, session_id: str) -> asyncio.Queue:
        """Registers a new event queue for WebSocket / SSE real-time streaming."""
        state = await self.get_session_state(session_id)
        queue = asyncio.Queue()
        state.subscribers.add(queue)
        return queue

    async def unsubscribe(self, session_id: str, queue: asyncio.Queue):
        """Unregisters an event queue."""
        state = await self.get_session_state(session_id)
        state.subscribers.discard(queue)

    async def broadcast(self, session_id: str, event: Dict[str, Any]):
        """Broadcasts event payload to all active session subscribers."""
        state = await self.get_session_state(session_id)
        dead_queues = set()
        for q in list(state.subscribers):
            try:
                q.put_nowait(event)
            except Exception:
                dead_queues.add(q)
        for q in dead_queues:
            state.subscribers.discard(q)

    async def run_prompt_task(self, session_id: str, user_prompt: str) -> bool:
        """
        Triggers agent sampling loop in the background while acquiring per-session lock.
        Returns False if session is currently busy processing another prompt.
        """
        state = await self.get_session_state(session_id)
        
        if state.lock.locked():
            return False  # Prevent race conditions: Session busy

        task = asyncio.create_task(self._execute_agent_loop(session_id, user_prompt))
        state.current_task = task
        return True

    async def stop_session_task(self, session_id: str) -> bool:
        """Interrupts and stops an ongoing agent task for the session."""
        state = await self.get_session_state(session_id)
        if state.current_task and not state.current_task.done():
            state.current_task.cancel()
            state.status = "stopped"
            await self.broadcast(session_id, {"type": "status", "status": "Execution stopped by user."})
            return True
        return False

    async def _execute_agent_loop(self, session_id: str, user_prompt: str):
        state = await self.get_session_state(session_id)

        async with state.lock:
            state.status = "running"
            await self.broadcast(session_id, {"type": "status", "status": "Session started processing prompt."})

            async with AsyncSessionLocal() as db:
                # 1. Load history from database
                history_messages = await self._load_chat_history(db, session_id)

                # 2. Append user prompt to DB
                user_msg = MessageModel(
                    session_id=session_id,
                    role="user",
                    content=user_prompt
                )
                db.add(user_msg)
                
                # Update session status in DB
                sess_stmt = select(SessionModel).where(SessionModel.id == session_id)
                sess_res = await db.execute(sess_stmt)
                db_sess = sess_res.scalar_one_or_none()
                if db_sess:
                    db_sess.status = "running"
                await db.commit()

                # Build Anthropic message thread ensuring tool_use blocks are followed by matching tool_result blocks
                anthropic_messages = self._build_anthropic_messages(history_messages, user_prompt)

                # Broadcast user prompt event to subscribers
                await self.broadcast(session_id, {"type": "user_message", "content": user_prompt})


                # 3. Execute sampling loop with real-time event broadcasting
                accumulated_text = ""
                tool_calls = []
                screenshots = []

                try:
                    display_info = await display_manager.get_or_create_display(session_id)
                    session_display = display_info.display_str
                    agent_model = db_sess.model if (db_sess and db_sess.model) else "claude-3-5-sonnet-20241022"
                    async for event in sampling_loop(messages=anthropic_messages, model=agent_model, display=session_display, session_id=session_id):
                        event_type = event.get("type")

                        await self.broadcast(session_id, event)

                        if event_type == "text":
                            accumulated_text += event.get("text", "")
                        elif event_type == "tool_use":
                            tool_calls.append(event)
                        elif event_type == "tool_result":
                            if event.get("base64_image"):
                                screenshots.append(event.get("base64_image"))

                    # 4. Save assistant response to DB
                    assistant_msg = MessageModel(
                        session_id=session_id,
                        role="assistant",
                        content=accumulated_text,
                        tool_calls=tool_calls if tool_calls else None,
                        screenshots=screenshots if screenshots else None
                    )
                    db.add(assistant_msg)
                    
                    if db_sess:
                        db_sess.status = "idle"
                    await db.commit()

                    state.status = "idle"
                    await self.broadcast(session_id, {"type": "status", "status": "Idle"})

                except asyncio.CancelledError:
                    if db_sess:
                        db_sess.status = "stopped"
                    await db.commit()
                    state.status = "stopped"
                    logger.info(f"Session {session_id} execution cancelled.")
                except Exception as e:
                    logger.error(f"Error in agent execution for session {session_id}: {str(e)}")
                    if db_sess:
                        db_sess.status = "error"
                    await db.commit()
                    state.status = "error"
                    await self.broadcast(session_id, {"type": "error", "error": str(e)})

    async def _load_chat_history(self, db: AsyncSession, session_id: str) -> List[MessageModel]:
        stmt = (
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.created_at)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    def _build_anthropic_messages(self, history_messages: List[MessageModel], new_user_prompt: str) -> List[Dict[str, Any]]:

        anthropic_messages = []
        
        for m in history_messages:
            if m.role == "user":
                if m.content:
                    anthropic_messages.append({"role": "user", "content": m.content})
            elif m.role == "assistant":
                blocks = []
                if m.content:
                    blocks.append({"type": "text", "text": m.content})
                
                tool_ids = []
                if m.tool_calls:
                    for tc in m.tool_calls:
                        tc_id = tc.get("id") or tc.get("tool_use_id")
                        if tc_id:
                            tool_ids.append(tc_id)
                            blocks.append({
                                "type": "tool_use",
                                "id": tc_id,
                                "name": tc.get("name"),
                                "input": tc.get("input", {})
                            })
                
                if blocks:
                    anthropic_messages.append({"role": "assistant", "content": blocks})
                
                # Ensure tool_use blocks are immediately followed by corresponding tool_result blocks
                if tool_ids:
                    tool_result_blocks = []
                    for tid in tool_ids:
                        tool_result_blocks.append({
                            "type": "tool_result",
                            "tool_use_id": tid,
                            "content": "Action completed successfully."
                        })
                    anthropic_messages.append({"role": "user", "content": tool_result_blocks})

        anthropic_messages.append({"role": "user", "content": new_user_prompt})
        return anthropic_messages

# Global Singleton Instance
session_manager = SessionManager()

