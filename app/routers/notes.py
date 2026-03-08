from fastapi import APIRouter, Depends, HTTPException, status,BackgroundTasks
from bson import ObjectId
from app.database import get_db
from app.schemas import NoteCreate, NoteUpdate
from datetime import datetime

from app.biometric_engine import BiometricBrain
from app.context_engine import ContextAnalyzer

router = APIRouter(prefix="/api/notes", tags=["Notes"])
brain = BiometricBrain()
context_engine = ContextAnalyzer()

def silent_model_adaptation(username: str, db):
    """
    Runs invisibly in the background. Uses a 'Core Anchor' approach 
    to prevent Data Poisoning / Imposter Drift.
    """
    try:
        # 1. Grab the most recent VERIFIED typing sessions (The "Adaptation")
        recent_cursor = db["biometric_history"].find(
            {"username": username, "event_type": "edit"} # "edit" represents recent notes
        ).sort("created_at", -1).limit(20)
        
        # 2. Grab the ORIGINAL Day-1 Calibration data (The "Core Anchor")
        anchor_cursor = db["biometric_history"].find(
            {"username": username, "event_type": "create"} # "create" is from Calibrate ID
        ).sort("created_at", 1).limit(10)
        
        valid_vectors = []
        
        # Helper to extract vectors safely
        def extract_vectors(cursor):
            for doc in cursor:
                if "vector_12" in doc:
                    vec_data = doc["vector_12"]
                    if len(vec_data) > 0 and isinstance(vec_data[0], list):
                        for chunk in vec_data:
                            if len(chunk) == 12: valid_vectors.append(chunk)
                    elif len(vec_data) == 12:
                        valid_vectors.append(vec_data)
                        
        extract_vectors(anchor_cursor) # Inject True North (Anchor)
        extract_vectors(recent_cursor) # Inject Recent Behavior (Drift)
        
        # If we have enough data, retrain the model!
        if len(valid_vectors) >= 5:
            brain.train_new_user(username, valid_vectors)
            print(f"🧠 [AUTO-ADAPT] Protected Model updated for {username}. Anchor + Recent Chunks: {len(valid_vectors)}")
            
    except Exception as e:
        print(f"⚠️ Auto-Adapt Error: {e}")

# --- CREATE ---
@router.post("/save", status_code=status.HTTP_201_CREATED)
def create_note(note: NoteCreate, background_tasks: BackgroundTasks, db = Depends(get_db)):
    try:
        notes_collection = db["user_notes"]
        bio_collection = db["biometric_history"] 
        
        # 1. Prepare Note Entry (Content only)
        note_entry = note.dict(exclude={"biometrics"}) 
        note_entry["created_at"] = datetime.now()
        note_entry["updated_at"] = None
        
        # 2. Live Risk Verification
        risk_data = {"status": "Unverified", "risk": 0}
        db_vector = None
        
        # --- NEW: Evaluate Contextual Risk (CP) ---
        cp_scores = {"IP": 0.05, "GEO": 0.05, "BT": 0.05, "CP_TOTAL": 0.05}
        if note.context:
            cp_scores = context_engine.evaluate_live_context(note.username, note.context.dict())

        if note.biometrics and isinstance(note.biometrics, list) and len(note.biometrics) > 0:
            # Check if it's an array of chunks (List[List[float]]) or a single chunk (List[float])
            if isinstance(note.biometrics[0], list):
                evaluate_vector = note.biometrics[-1] # Grab the latest chunk for the final score
                db_vector = note.biometrics         # Save the whole trajectory path
            elif len(note.biometrics) == 12:
                evaluate_vector = note.biometrics
                db_vector = [note.biometrics]       # Wrap in array to keep DB schema consistent
            else:
                evaluate_vector = None

            if evaluate_vector:
                # Verify against the user's trained model
                risk_data = brain.verify_live_data(note.username, evaluate_vector)

                # --- Attach CP data to the final risk output ---
                risk_data["context_scores"] = cp_scores
                note_entry["risk_analysis"] = risk_data
        
        # Insert Note
        note_result = notes_collection.insert_one(note_entry)
        note_id = note_result.inserted_id
        
        # 3. Archive Biometrics (History)
        if db_vector:
            bio_entry = {
                "username": note.username,
                "source_note_id": str(note_id),
                "session_id": note.sessionID,
                "vector_12": db_vector, # Now successfully stores the trajectory array!
                "created_at": datetime.now(),
                "event_type": "create"
            }
            bio_collection.insert_one(bio_entry)
        # If the user successfully verified, trigger background adaptation
        if risk_data.get("status") == "Verified":
            background_tasks.add_task(silent_model_adaptation, note.username, db)
            
        return {
            "success": True, 
            "id": str(note_id), 
            "risk_analysis": risk_data,
            "message": "Note saved & Biometrics Verified"
        }
    except Exception as e:
        print(f"Save Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    
# --- UPDATE ---
@router.put("/{note_id}")
def update_note(note_id: str, update: NoteUpdate, background_tasks: BackgroundTasks, db = Depends(get_db)):
    notes_collection = db["user_notes"]
    bio_collection = db["biometric_history"]
    
    # 1. Update the Note Content
    update_data = {k: v for k, v in update.dict(exclude={"biometrics"}).items() if v is not None}
    
    risk_data = None
    db_vector = None

    # 2. Live Risk Verification
    if update.biometrics and isinstance(update.biometrics, list) and len(update.biometrics) > 0:
        
        current_note = notes_collection.find_one({"_id": ObjectId(note_id)})
        if not current_note:
            raise HTTPException(status_code=404, detail="Note not found")
            
        username = current_note["username"]
        
        # Check array depth
        if isinstance(update.biometrics[0], list):
            evaluate_vector = update.biometrics[-1]
            db_vector = update.biometrics
        elif len(update.biometrics) == 12:
            evaluate_vector = update.biometrics
            db_vector = [update.biometrics]
        else:
            evaluate_vector = None

        if evaluate_vector:
            risk_data = brain.verify_live_data(username, evaluate_vector)
            update_data["risk_analysis"] = risk_data

    # Perform the Update
    if update_data:
        update_data["updated_at"] = datetime.now()
        
        result = notes_collection.update_one(
            {"_id": ObjectId(note_id)},
            {"$set": update_data}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Note not found")

    # 3. Archive New Biometrics (History)
    if db_vector:
        if 'username' not in locals():
             current_note = notes_collection.find_one({"_id": ObjectId(note_id)})
             username = current_note["username"]

        bio_entry = {
            "username": username,
            "source_note_id": note_id,
            "vector_12": db_vector, 
            "created_at": datetime.now(),
            "event_type": "edit"
        }
        bio_collection.insert_one(bio_entry)

    # If the user successfully verified during the edit, trigger background adaptation
    if risk_data and risk_data.get("status") == "Verified":
        background_tasks.add_task(silent_model_adaptation, username, db)

    return {
        "success": True, 
        "risk_analysis": risk_data, 
        "message": "Note updated & Trajectory archived"
    }

# --- READ (List) ---
@router.get("/list/{username}")
def get_user_notes(username: str, db = Depends(get_db)):
    collection = db["user_notes"]
    cursor = collection.find({"username": username}).sort("created_at", -1)
    
    notes = []
    for doc in cursor:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
        if "risk_analysis" not in doc:
             doc["risk_analysis"] = {"status": "Legacy", "risk": 0}
        notes.append(doc)
    return {"notes": notes}

# --- DELETE ---
@router.delete("/{note_id}")
def delete_note(note_id: str, db = Depends(get_db)):
    collection = db["user_notes"]
    result = collection.delete_one({"_id": ObjectId(note_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    
    return {"success": True, "message": "Note deleted, Biometrics preserved"}