from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db

router = APIRouter(prefix="/api/stats", tags=["Analytics"])

@router.get("/{username}")
def get_biometric_stats(username: str, db = Depends(get_db)):
    """Calculates Dwell & Flight averages for the graphs"""
    try:
        # CRITICAL: We now query 'user_notes', not 'keystroke_logs'
        collection = db["user_notes"]
        
        # 1. Fetch ALL sessions for this user, sorted by time (newest first)
        cursor = collection.find({"username": username}).sort("created_at", -1)
        all_sessions_raw = list(cursor)
        
        if not all_sessions_raw:
             return {
                "username": username,
                "dwell_data": {"average": {}, "recent": {}, "historical": []},
                "flight_data": {"average": {}, "recent": {}, "historical": []}
            }

        # --- Helper to format a session ---
        def format_session(session_doc):
            dwell_map = {}
            flight_map = {}
            
            logs = session_doc.get("keystrokeLog", [])
            
            # Sort by downTime to ensure chronological order (crucial for flight time)
            logs.sort(key=lambda x: x["downTime"])

            for i in range(len(logs)):
                curr = logs[i]
                key_char = curr["key"]
                
                # 1. Dwell Time
                if key_char not in dwell_map:
                    dwell_map[key_char] = {"total": 0, "count": 0}
                dwell_map[key_char]["total"] += curr["dwellTime"]
                dwell_map[key_char]["count"] += 1

                # 2. Flight Time (Current Down - Prev Up)
                if i > 0:
                    prev = logs[i-1]
                    flight = curr["downTime"] - prev["upTime"]
                    
                    if key_char not in flight_map:
                        flight_map[key_char] = {"total": 0, "count": 0}
                    flight_map[key_char]["total"] += flight
                    flight_map[key_char]["count"] += 1

            # Finalize Averages
            final_dwell = {k: round(v["total"] / v["count"]) for k, v in dwell_map.items()}
            final_flight = {k: round(v["total"] / v["count"]) for k, v in flight_map.items()}
            
            return {"dwell": final_dwell, "flight": final_flight}

        # 2. Process Data
        recent_processed = format_session(all_sessions_raw[0]) # Newest
        historical_processed = [format_session(doc) for doc in all_sessions_raw[1:]] # History

        # 3. Calculate Global Averages
        def calculate_global_avg(dataset, metric_key):
            temp_map = {}
            # Combine recent + historical for the global average
            for session in dataset:
                data = session[metric_key]
                for k, v in data.items():
                    if k not in temp_map: temp_map[k] = []
                    temp_map[k].append(v)
            return {k: round(sum(v)/len(v)) for k, v in temp_map.items()}

        all_processed = [recent_processed] + historical_processed
        
        avg_dwell_profile = calculate_global_avg(all_processed, "dwell")
        avg_flight_profile = calculate_global_avg(all_processed, "flight")

        return {
            "username": username,
            "dwell_data": {
                "recent": recent_processed["dwell"],
                "historical": [h["dwell"] for h in historical_processed],
                "average": avg_dwell_profile
            },
            "flight_data": {
                "recent": recent_processed["flight"],
                "historical": [h["flight"] for h in historical_processed],
                "average": avg_flight_profile
            }
        }

    except Exception as e:
        print(f"Stats Error: {e}")
        raise HTTPException(status_code=500, detail="Stats calculation failed")