from fastapi import APIRouter, Body, Depends, HTTPException
from app.database import get_db
from app.biometric_engine import BiometricBrain

brain = BiometricBrain()


# Prefix is "/api/users", so the root "/" becomes "http://.../api/users"
router = APIRouter(prefix="/api/users", tags=["Users"])

@router.get("/")
def get_active_users(db = Depends(get_db)):
    """Fetches all unique usernames from the notes collection"""
    try:
        # We now query 'user_notes' since that's where we save data
        collection = db["user_notes"]
        users = collection.distinct("username")
        return {"users": users}
    except Exception as e:
        print(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch users")
    

@router.post("/train")
def train_user(data: dict = Body(...)):
    username = data.get("username")
    vectors = data.get("vectors") # Expecting List[List[float]]
    
    if not vectors or len(vectors) < 3:
        raise HTTPException(status_code=400, detail="Need at least 3 samples to calibrate")
    
    result = brain.train_new_user(username, vectors)
    return result