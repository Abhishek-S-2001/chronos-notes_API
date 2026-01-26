from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# --- Privacy-Focused Biometric Model ---
class BiometricData(BaseModel):
    finger: str           # <--- New Feature: "L.Index", "R.Pinky", etc.
    dwellTime: float      # Physics: Hold Duration
    flightTime: float     # Physics: Latency (Reflex)
    timestamp: float      # Time-series data
    downDownTime: Optional[float] = 0.0 # Kept for backward compatibility

# --- Note CRUD Models ---
class NoteBase(BaseModel):
    title: str
    content: str

class NoteCreate(NoteBase):
    sessionID: str
    username: str
    platform: Optional[str] = "Web"
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