import asyncio
import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.db.models import SessionModel, MessageModel
from app.db.schemas import (
    SessionCreate,
    SessionResponse,
    SessionUpdate,
    MessageResponse,
    UserPromptRequest,
)
from app.services.session_manager import session_manager

router = APIRouter(prefix="/sessions", tags=["Sessions"])

@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(session_in: SessionCreate, db: AsyncSession = Depends(get_db)):
    """Creates a new computer use agent session."""
    new_session = SessionModel(
        title=session_in.title or "New Session",
        model=session_in.model or "claude-3-5-sonnet-20241022",
        status="idle"
    )
    db.add(new_session)
    await db.commit()
    
    # Reload session with messages relationship preloaded
    stmt = select(SessionModel).options(selectinload(SessionModel.messages)).where(SessionModel.id == new_session.id)
    res = await db.execute(stmt)
    return res.scalar_one()

@router.get("", response_model=List[SessionResponse])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """Lists all agent sessions sorted by creation time."""
    stmt = select(SessionModel).options(selectinload(SessionModel.messages)).order_by(SessionModel.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieves session details and metadata."""
    stmt = select(SessionModel).options(selectinload(SessionModel.messages)).where(SessionModel.id == session_id)
    res = await db.execute(stmt)
    sess = res.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return sess

@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Deletes a session and its message history."""
    stmt = select(SessionModel).where(SessionModel.id == session_id)
    res = await db.execute(stmt)
    sess = res.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    
    # Interrupt task if running
    await session_manager.stop_session_task(session_id)

    await db.delete(sess)
    await db.commit()
    return None

@router.get("/{session_id}/messages", response_model=List[MessageResponse])
async def get_session_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    """Fetches chat/event message history for a session."""
    stmt = select(MessageModel).where(MessageModel.session_id == session_id).order_by(MessageModel.created_at.asc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/{session_id}/messages", status_code=status.HTTP_202_ACCEPTED)
async def send_session_message(
    session_id: str,
    payload: UserPromptRequest,
    db: AsyncSession = Depends(get_db)
):
    """Sends a user instruction/prompt to start agent execution. Returns 409 if session is busy."""
    stmt = select(SessionModel).where(SessionModel.id == session_id)
    res = await db.execute(stmt)
    sess = res.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    success = await session_manager.run_prompt_task(session_id, payload.prompt)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is currently busy processing another request. Please wait."
        )

    return {"status": "accepted", "message": "Agent sampling loop started in background."}

@router.post("/{session_id}/stop")
async def stop_session_message(session_id: str, db: AsyncSession = Depends(get_db)):
    """Interrupts active task execution for a session."""
    stmt = select(SessionModel).where(SessionModel.id == session_id)
    res = await db.execute(stmt)
    sess = res.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    stopped = await session_manager.stop_session_task(session_id)
    if stopped:
        sess.status = "stopped"
        await db.commit()
        return {"status": "success", "message": "Task execution interrupted."}
    return {"status": "idle", "message": "No active task was running for this session."}

# --- Real-Time Streaming Endpoints ---

@router.websocket("/ws/{session_id}")
async def websocket_session_stream(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time progress streaming of agent execution."""
    await websocket.accept()
    queue = await session_manager.subscribe(session_id)
    
    try:
        # Send initial status
        state = await session_manager.get_session_state(session_id)
        await websocket.send_json({"type": "status", "status": state.status})

        while True:
            event = await queue.get()
            await websocket.send_json(event)

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await session_manager.unsubscribe(session_id, queue)

@router.get("/{session_id}/stream")
async def sse_session_stream(session_id: str):
    """Server-Sent Events (SSE) stream endpoint for real-time progress updates."""
    queue = await session_manager.subscribe(session_id)

    async def event_generator():
        try:
            state = await session_manager.get_session_state(session_id)
            yield f"data: {json.dumps({'type': 'status', 'status': state.status})}\n\n"

            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await session_manager.unsubscribe(session_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
