from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db
from app.schemas import NoteCreateRequest
from datetime import datetime

router = APIRouter(prefix="/api/notes", tags=["Notes"])

@APIRouter.post("/save") # Becomes /api/notes/save
def create_note(note: NoteCreateRequest, db = Depends(get_db)):
    """Saves a note content AND its biometric keystroke logs"""
    try:
        collection = db["user_notes"] # New collection for notes
        
        entry = note.dict()
        entry["created_at"] = datetime.now()
        
        result = collection.insert_one(entry)
        
        return {
            "success": True,
            "message": "Note and biometrics saved",
            "id": str(result.inserted_id)
        }
    except Exception as e:
        print(f"Error saving note: {e}")
        raise HTTPException(status_code=500, detail="Failed to save note")

@APIRouter.get("/list/{username}")
def get_user_notes(username: str, db = Depends(get_db)):
    """Fetches real notes for the 'My Notes' grid"""
    try:
        collection = db["user_notes"]
        # Fetch notes, hide the keystrokeLog to save bandwidth
        cursor = collection.find(
            {"username": username}, 
            {"keystrokeLog": 0} # Exclude huge log arrays
        ).sort("created_at", -1)
        
        notes = []
        for doc in cursor:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
            notes.append(doc)
            
        return {"notes": notes}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch notes")
    