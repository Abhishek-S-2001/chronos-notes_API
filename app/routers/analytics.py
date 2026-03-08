import os
import pickle
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from app.database import get_db

from pydantic import BaseModel
from typing import List
from app.biometric_engine import BiometricBrain

brain = BiometricBrain()

class LiveVerifyPayload(BaseModel):
    username: str
    vector: List[float]


router = APIRouter(prefix="/api/stats", tags=["Analytics"])

MODEL_FEATURES = [
    'Dwell_Mean', 'Dwell_Min', 'Dwell_Max', 
    'Flight_Mean', 'Flight_Min', 'Flight_Max', 
    'DD_Mean', 'DD_Min', 'DD_Max', 
    'UU_Mean', 'UU_Min', 'UU_Max'
]

# ---------------------------------------------------------
# 1. SPECIFIC NOTE STATS (Used by ViewNoteModal)
# ---------------------------------------------------------
@router.get("/note/{note_id}")
def get_note_risk_score(note_id: str, db = Depends(get_db)):
    """
    Fetches the Risk Score for a SPECIFIC note based on the 
    BiometricBrain analysis saved during creation/editing.
    """
    try:
        note = db["user_notes"].find_one({"_id": ObjectId(note_id)})
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")

        risk_analysis = note.get("risk_analysis", {})
        raw_risk = risk_analysis.get("risk", 0) 
        status = risk_analysis.get("status", "Unverified")
        
        sensitivity = note.get("sensitivity", 5)
        risk_multiplier = sensitivity / 5.0
        
        final_risk = min(100, raw_risk * risk_multiplier)
        trust_score = max(0, 100 - final_risk)

        return {
            "risk_score": round(final_risk),
            "trust_score": round(trust_score),
            "status": status,
            "sensitivity": sensitivity,
            "raw_risk": raw_risk
        }

    except Exception as e:
        print(f"Note Stats Error: {e}")
        raise HTTPException(status_code=500, detail="Calculation failed")


# ---------------------------------------------------------
# 2. GLOBAL USER DNA (Used by Dashboard Visuals)
# ---------------------------------------------------------
@router.get("/{username}")
def get_user_dna_visuals(username: str, db = Depends(get_db)):
    try:
        safe_id = "".join([c for c in username if c.isalnum()])
        model_path = f"user_models/user_{safe_id}.pkl"
        
        if not os.path.exists(model_path):
            return {"radar_data": [], "scatter_data": None}
            
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
            
        scaler = model['scaler']
        pca = model['pca']
        centroid_2d = model['centroid']
        threshold = model['threshold']

        # Get latest raw typing vector from DB
        latest_doc = db["biometric_history"].find_one(
            {"username": username}, 
            sort=[("created_at", -1)]
        )
        
        baseline_12d = scaler.mean_ 
        raw_latest_vector = latest_doc.get("vector_12") if latest_doc else None
        latest_12d = baseline_12d
        
        if raw_latest_vector and len(raw_latest_vector) > 0:
            if isinstance(raw_latest_vector[0], list):
                latest_12d = raw_latest_vector[-1]
            else:
                latest_12d = raw_latest_vector
        
        # --- 1. Radar Data ---
        radar_data = []
        for i, feat in enumerate(MODEL_FEATURES):
            radar_data.append({
                "feature": feat,
                "baseline": round(float(baseline_12d[i]), 1),
                "latest": round(float(latest_12d[i]), 1)
            })
            
        # --- 2. Historical Data (THE FIX IS HERE) ---
        historical_points = []
        
        # A. Inject the 50-point grey cloud from calibration
        training_cloud = model.get('training_cloud_2d', [])
        for pt in training_cloud:
            historical_points.append({
                "x": round(float(pt[0]), 3), 
                "y": round(float(pt[1]), 3)
            })
            
        # B. Inject actual history dots from MongoDB
        hist_docs = list(db["biometric_history"].find({"username": username}).limit(50))
        for doc in hist_docs:
            if "vector_12" in doc:
                vec_data = doc["vector_12"]
                if len(vec_data) > 0:
                    hist_vec = vec_data[-1] if isinstance(vec_data[0], list) else vec_data
                    if len(hist_vec) == 12: 
                        vec = np.array(hist_vec).reshape(1, -1)
                        scaled = scaler.transform(vec)
                        pca_pt = pca.transform(scaled)[0]
                        historical_points.append({"x": round(float(pca_pt[0]), 3), "y": round(float(pca_pt[1]), 3)})
                
        # --- 3. Live Trajectory Path ---
        latest_2d = []
        if raw_latest_vector and len(raw_latest_vector) > 0:
            if isinstance(raw_latest_vector[0], list):
                for vec in raw_latest_vector:
                    if len(vec) == 12:
                        v = np.array(vec).reshape(1, -1)
                        scaled = scaler.transform(v)
                        pca_pt = pca.transform(scaled)[0]
                        dist = float(np.linalg.norm(pca_pt - centroid_2d))
                        latest_2d.append({
                            "x": round(float(pca_pt[0]), 3),
                            "y": round(float(pca_pt[1]), 3),
                            "isAnomaly": dist > threshold
                        })
            else:
                if len(raw_latest_vector) == 12:
                    v = np.array(raw_latest_vector).reshape(1, -1)
                    scaled = scaler.transform(v)
                    pca_pt = pca.transform(scaled)[0]
                    dist = float(np.linalg.norm(pca_pt - centroid_2d))
                    latest_2d.append({
                        "x": round(float(pca_pt[0]), 3),
                        "y": round(float(pca_pt[1]), 3),
                        "isAnomaly": dist > threshold
                    })
            
        return {
            "radar_data": radar_data,
            "scatter_data": {
                "historical": historical_points,
                "centroid": {"x": round(float(centroid_2d[0]), 3), "y": round(float(centroid_2d[1]), 3)},
                "latest": latest_2d,
                "threshold": round(float(threshold), 3)
            }
        }

    except Exception as e:
        print(f"Visuals Error: {e}")
        return {"radar_data": [], "scatter_data": None}
    

@router.post("/verify_live")
def verify_live_typing(payload: LiveVerifyPayload):
    """
    Called every 20 keystrokes from the frontend to provide a live floating risk score.
    """
    try:
        result = brain.verify_live_data(payload.username, payload.vector)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))