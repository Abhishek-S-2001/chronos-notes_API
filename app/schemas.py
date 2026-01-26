from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


# --- Privacy-Focused Keystroke Model ---
# No 'key' or 'code' fields. Only pure physics.
class BiometricData(BaseModel):
    dwellTime: float  # H
    flightTime: float # UD
    downDownTime: float # DD

# --- Note CRUD Models ---
class NoteBase(BaseModel):
    title: str
    content: str

class NoteCreate(NoteBase):
    sessionID: str
    username: str
    platform: Optional[str] = "Web"
    # The pure mathematical sequence
    biometrics: List[BiometricData] 

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    biometrics: Optional[List[BiometricData]] = None

class NoteResponse(NoteBase):
    id: str
    username: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    # We generally don't return the huge biometric log in the list view