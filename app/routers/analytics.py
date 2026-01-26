from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db
import math

router = APIRouter(prefix="/api/stats", tags=["Analytics"])

def calculate_histogram(values, step=20, max_val=400):
    """Converts a list of timings into a percentage distribution"""
    if not values: 
        return {i: 0 for i in range(0, max_val, step)}
    
    total = len(values)
    dist = {}
    for i in range(0, max_val, step):
        count = sum(1 for x in values if i <= x < i+step)
        dist[i] = (count / total) * 100
    return dist

def calculate_deviation(dist1, dist2):
    """
    Simple Anomaly Score: Euclidean Distance between two distributions.
    Returns a score 0.0 (Identical) to 100.0 (Completely Different).
    """
    error = 0
    keys = set(dist1.keys()) | set(dist2.keys())
    for k in keys:
        v1 = dist1.get(k, 0)
        v2 = dist2.get(k, 0)
        error += (v1 - v2) ** 2
    return math.sqrt(error)

@router.get("/{username}")
def get_biometric_stats(username: str, db = Depends(get_db)):
    try:
        # CRITICAL CHANGE: Query 'biometric_history' instead of 'user_notes'
        bio_collection = db["biometric_history"]
        
        # Fetch all biometric sessions for this user
        cursor = bio_collection.find({"username": username}).sort("created_at", -1)
        sessions = list(cursor)
        
        if not sessions:
             return {"username": username, "chart_data": [], "anomaly_score": 0, "is_anomaly": False}

        # 1. Prepare Data Pools
        # The "Recent" one is the very last typing session (Edit or Create)
        recent_session = sessions[0] 
        history_sessions = sessions[1:]

        recent_dwells = [b["dwellTime"] for b in recent_session.get("biometrics", [])]
        
        # 2. Calculate Individual Histograms (Faint Lines)
        history_distributions = []
        all_dwells_combined = [] 

        for session in history_sessions:
            dwells = [b["dwellTime"] for b in session.get("biometrics", [])]
            if dwells:
                dist = calculate_histogram(dwells)
                history_distributions.append(dist)
                all_dwells_combined.extend(dwells)

        # 3. Calculate Average Profile (Bold Blue Line)
        avg_dist = calculate_histogram(all_dwells_combined)
        
        # 4. Calculate Recent Profile (Active Line)
        recent_dist = calculate_histogram(recent_dwells)

        # 5. Anomaly Detection
        anomaly_score = calculate_deviation(recent_dist, avg_dist)
        is_anomaly = anomaly_score > 30.0 

        # 6. Format for Chart
        chart_data = []
        ranges = sorted(avg_dist.keys())
        
        for r in ranges:
            point = {
                "range": r,
                "Average": round(avg_dist.get(r, 0), 1),
                "Recent": round(recent_dist.get(r, 0), 1),
            }
            # Add faint history points
            for idx, hist in enumerate(history_distributions[:10]): 
                point[f"history_{idx}"] = round(hist.get(r, 0), 1)
            
            chart_data.append(point)

        return {
            "username": username,
            "dwell_data": chart_data,
            "flight_data": chart_data, # (Duplicate logic for flight if needed)
            "anomaly_score": round(anomaly_score, 2),
            "is_anomaly": is_anomaly
        }

    except Exception as e:
        print(f"Stats Error: {e}")
        raise HTTPException(status_code=500, detail="Stats calculation failed")