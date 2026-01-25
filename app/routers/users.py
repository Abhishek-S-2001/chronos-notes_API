from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db

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