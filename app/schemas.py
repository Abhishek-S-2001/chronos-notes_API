from pydantic import BaseModel
from typing import List, Optional, Union
from datetime import datetime


# --- Context Data Schema ---
class ContextData(BaseModel):
    ip: str
    geo: str
    user_agent: str
    screen: str

# --- Biometric Data Models ---

# (Optional) Keep this for legacy support or detailed logging if needed
class BiometricData(BaseModel):
    finger: str
    dwellTime: float
    flightTime: float
    timestamp: float

# --- Note CRUD Models ---

class NoteBase(BaseModel):
    title: str
    content: str

class NoteCreate(BaseModel):
    sessionID: str
    username: str
    title: str
    content: str
    platform: Optional[str] = "Web"
    biometrics: Union[List[float], List[List[float]], List[BiometricData]]
    sensitivity: Optional[int] = 5
    context: Optional[ContextData] = None

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    biometrics: Optional[Union[List[float], List[BiometricData]]] = None
    sensitivity: Optional[int] = None

class NoteResponse(NoteBase):
    id: str
    username: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    sensitivity: int = 5
    # Return the analysis result if available
    risk_analysis: Optional[dict] = None