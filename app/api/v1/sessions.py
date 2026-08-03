import asyncio
import json
import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import StreamingResponse, FileResponse
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
from app.services.display_manager import display_manager

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

    # Release virtual X display & VNC resources
    await display_manager.release_display(session_id)

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

@router.get("/{session_id}/files")
async def list_session_files(session_id: str, db: AsyncSession = Depends(get_db)):
    """Lists generated/output files in the session workspace."""
    stmt = select(SessionModel).where(SessionModel.id == session_id)
    res = await db.execute(stmt)
    sess = res.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    workspace_dir = await session_manager.get_session_workspace(session_id)
    file_list = []
    if os.path.exists(workspace_dir):
        for root, dirs, files in os.walk(workspace_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, workspace_dir)
                stat = os.stat(full_path)
                file_list.append({
                    "name": file,
                    "path": rel_path,
                    "size_bytes": stat.st_size,
                    "modified_at": stat.st_mtime
                })
    return {"session_id": session_id, "files": file_list}

@router.get("/{session_id}/files/download")
async def download_session_file(
    session_id: str,
    filepath: str = Query(..., description="Relative path of file in workspace"),
    db: AsyncSession = Depends(get_db)
):
    """Downloads a file from the session workspace."""
    stmt = select(SessionModel).where(SessionModel.id == session_id)
    res = await db.execute(stmt)
    sess = res.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    workspace_dir = await session_manager.get_session_workspace(session_id)
    target_path = os.path.abspath(os.path.join(workspace_dir, filepath))

    # Prevent path traversal outside workspace_dir
    if not target_path.startswith(os.path.abspath(workspace_dir)):
        raise HTTPException(status_code=400, detail="Invalid file path.")

    if not os.path.exists(target_path) or not os.path.isfile(target_path):
        raise HTTPException(status_code=404, detail=f"File '{filepath}' not found.")

    return FileResponse(path=target_path, filename=os.path.basename(target_path))

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

@router.websocket("/{session_id}/vnc")
async def websocket_vnc_proxy(websocket: WebSocket, session_id: str):
    """WebSocket proxy endpoint connecting browser noVNC client to session-isolated VNC RFB port."""
    await websocket.accept()
    
    display_info = await display_manager.get_or_create_display(session_id)
    vnc_port = display_info.vnc_port

    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", vnc_port)
    except Exception as e:
        await websocket.close(code=1011, reason=f"Failed to connect to VNC port {vnc_port}: {str(e)}")
        return

    async def ws_to_tcp():
        try:
            while True:
                data = await websocket.receive_bytes()
                writer.write(data)
                await writer.drain()
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception:
            pass

    async def tcp_to_ws():
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                await websocket.send_bytes(data)
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception:
            pass

    t1 = asyncio.create_task(ws_to_tcp())
    t2 = asyncio.create_task(tcp_to_ws())

    done, pending = await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()

    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass

