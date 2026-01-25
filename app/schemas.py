from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# --- Sub-models ---
class Keystroke(BaseModel):
    key: str
    code: str
    downTime: float
    upTime: float
    dwellTime: float

# --- Request Models (What frontend sends) ---
class NoteCreateRequest(BaseModel):
    sessionID: str
    username: str
    title: str
    content: str  # <--- NEW: Actually storing the note text now!
    keystrokeLog: List[Keystroke]
    platform: Optional[str] = "Web"

# --- Response Models (What we send back) ---
class NoteResponse(BaseModel):
    id: str
    title: str
    content: str
    created_at: datetime