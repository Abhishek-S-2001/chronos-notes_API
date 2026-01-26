from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db
import math

router = APIRouter(prefix="/api/stats", tags=["Analytics"])

@router.get("/{username}")
def get_biometric_stats(username: str, db = Depends(get_db)):
    try:
        bio_collection = db["biometric_history"]
        
        # Fetch last 50 sessions (we need a lot of dots for the cloud)
        cursor = bio_collection.find({"username": username}).sort("created_at", -1).limit(50)
        sessions = list(cursor)
        
        if not sessions:
             return {"username": username, "radar_data": [], "scatter_data": []}

        recent_session = sessions[0].get("biometrics", [])
        
        # --- 1. Fingerprint Radar (Agility Profile) ---
        # Calculate Average Dwell Time per Finger for the User's History
        finger_map = {} # { "L.Pinky": [100, 120, ...], ... }
        all_fingers = ["L.Pinky", "L.Ring", "L.Mid", "L.Index", "Thumb", "R.Index", "R.Mid", "R.Ring", "R.Pinky"]

        # Aggregate history data
        for session in sessions:
            for b in session.get("biometrics", []):
                f = b.get("finger", "Other")
                if f in all_fingers:
                    if f not in finger_map: finger_map[f] = []
                    finger_map[f].append(b["dwellTime"])

        radar_data = []
        for f in all_fingers:
            dwells = finger_map.get(f, [])
            avg_speed = sum(dwells) / len(dwells) if dwells else 0
            # Invert Logic: Lower Dwell = Higher Agility (Speed)
            # We map 50ms -> 100 Agility, 200ms -> 0 Agility for visual "Pop"
            agility_score = max(0, min(100, 150 - avg_speed))
            
            radar_data.append({
                "finger": f,
                "agility": round(agility_score),
                "avg_dwell": round(avg_speed)
            })

        # --- 2. Rhythm Cloud (Scatter Plot) ---
        # X = Flight Time (Reflex), Y = Dwell Time (Press)
        # We take the last 200 keystrokes from history to form the "Cloud"
        scatter_data = []
        
        # Add History Points (Gray/Faint)
        for session in sessions[1:5]: # Last 5 sessions
            for b in session.get("biometrics", []):
                # Filter outliers for cleaner graph
                if b["flightTime"] < 500 and b["dwellTime"] < 300:
                    scatter_data.append({
                        "x": b["flightTime"],
                        "y": b["dwellTime"],
                        "type": "history" 
                    })

        # Add Recent Points (Colored)
        for b in recent_session:
             if b["flightTime"] < 500 and b["dwellTime"] < 300:
                scatter_data.append({
                    "x": b["flightTime"],
                    "y": b["dwellTime"],
                    "type": "current",
                    "finger": b.get("finger", "?")
                })

        return {
            "username": username,
            "radar_data": radar_data,
            "scatter_data": scatter_data
        }

    except Exception as e:
        print(f"Stats Error: {e}")
        raise HTTPException(status_code=500, detail="Stats calculation failed")