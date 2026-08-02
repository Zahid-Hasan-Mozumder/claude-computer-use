from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field

# --- Message Schemas ---
class MessageBase(BaseModel):
    role: str
    content: Optional[str] = ""
    tool_calls: Optional[Any] = None
    screenshots: Optional[List[str]] = None

class MessageCreate(MessageBase):
    pass

class MessageResponse(MessageBase):
    id: str
    session_id: str
    created_at: datetime

    class Config:
        from_attributes = True

# --- Session Schemas ---
class SessionCreate(BaseModel):
    title: Optional[str] = "New Session"
    model: Optional[str] = "claude-3-5-sonnet-20241022"

class SessionUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None

class SessionResponse(BaseModel):
    id: str
    title: str
    model: str
    status: str
    created_at: datetime
    updated_at: datetime
    messages: Optional[List[MessageResponse]] = []

    class Config:
        from_attributes = True

# --- User Input Payload Schema ---
class UserPromptRequest(BaseModel):
    prompt: str = Field(..., description="User prompt/instruction for the agent")
