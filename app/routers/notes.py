from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from app.database import get_db
from app.schemas import NoteCreate, NoteUpdate, NoteResponse
from datetime import datetime

router = APIRouter(prefix="/api/notes", tags=["Notes"])

# --- CREATE (Decoupled) ---
@router.post("/save", status_code=status.HTTP_201_CREATED)
def create_note(note: NoteCreate, db = Depends(get_db)):
    try:
        notes_collection = db["user_notes"]
        bio_collection = db["biometric_history"] # <--- NEW COLLECTION
        
        # 1. Save the Note (Content only)
        note_entry = note.dict(exclude={"biometrics"}) # Remove bio from note
        note_entry["created_at"] = datetime.now()
        note_entry["updated_at"] = None
        
        note_result = notes_collection.insert_one(note_entry)
        note_id = note_result.inserted_id
        
        # 2. Save the Biometrics (Separately)
        if note.biometrics:
            bio_entry = {
                "username": note.username,
                "source_note_id": str(note_id), # Link it just in case
                "session_id": note.sessionID,
                "biometrics": [b.dict() for b in note.biometrics], # Store raw list
                "created_at": datetime.now(),
                "event_type": "create"
            }
            bio_collection.insert_one(bio_entry)
        
        return {
            "success": True, 
            "id": str(note_id), 
            "message": "Note saved & Biometrics archived separately"
        }
    except Exception as e:
        print(f"Save Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- UPDATE (Decoupled) ---
@router.put("/{note_id}")
def update_note(note_id: str, update: NoteUpdate, db = Depends(get_db)):
    notes_collection = db["user_notes"]
    bio_collection = db["biometric_history"]
    
    # 1. Update the Note Content
    update_data = {k: v for k, v in update.dict(exclude={"biometrics"}).items() if v is not None}
    
    if update_data:
        update_data["updated_at"] = datetime.now()
        
        result = notes_collection.update_one(
            {"_id": ObjectId(note_id)},
            {"$set": update_data}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Note not found")

    # 2. Archive New Biometrics (If any)
    # We do NOT update the old bio entry. We create a NEW one (more training data!)
    if update.biometrics:
        # We need the username, so we fetch the note first
        current_note = notes_collection.find_one({"_id": ObjectId(note_id)})
        if current_note:
            bio_entry = {
                "username": current_note["username"],
                "source_note_id": note_id,
                "biometrics": [b.dict() for b in update.biometrics],
                "created_at": datetime.now(),
                "event_type": "edit"
            }
            bio_collection.insert_one(bio_entry)

    return {"success": True, "message": "Note updated & New biometrics archived"}

# --- READ (List) ---
@router.get("/list/{username}")
def get_user_notes(username: str, db = Depends(get_db)):
    collection = db["user_notes"]
    # We no longer need to exclude 'biometrics' because they aren't here anymore!
    cursor = collection.find({"username": username}).sort("created_at", -1)
    
    notes = []
    for doc in cursor:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
        notes.append(doc)
    return {"notes": notes}

# --- DELETE ---
@router.delete("/{note_id}")
def delete_note(note_id: str, db = Depends(get_db)):
    collection = db["user_notes"]
    result = collection.delete_one({"_id": ObjectId(note_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
        
    # NOTE: We intentionally DO NOT delete from 'biometric_history'
    # This preserves the training data even if the user deletes the note.
    
    return {"success": True, "message": "Note deleted, Biometrics preserved"}