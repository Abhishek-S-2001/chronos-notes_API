from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
# import pymongo
# from pymongo.errors import ConnectionFailure, ConfigurationError
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# --- Configuration ---
app = FastAPI()

# 1. CORS Setup (Crucial for connecting to Next.js)
# This allows your Next.js app (localhost:3000) to talk to this Python API (localhost:8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 2. Database Connection
collection = None
uri = "mongodb+srv://chronos_user:chronos1234@cluster0.7uk2k1l.mongodb.net/?appName=Cluster0"

# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

class Keystroke(BaseModel):
    key: str
    code: str
    downTime: float
    upTime: float
    dwellTime: float

class SessionData(BaseModel):
    sessionID: str
    noteTitle: str
    keystrokeLog: List[Keystroke]
    platform: Optional[str] = "Mac/Web"
    timestamp: Optional[str] = None

# --- API Endpoints ---

@app.get("/")
def read_root():
    return {"status": "Active", "service": "Chronos Anomaly Detector API"}

@app.post("/api/save-metrics")
def save_metrics(data: SessionData):
    try:
        # Convert Pydantic model to a Python dictionary
        entry = data.dict()
        
        # Add a server-side timestamp
        entry["received_at"] = datetime.now()
        
        # Insert into MongoDB
        result = collection.insert_one(entry)
        
        return {
            "success": True, 
            "message": "Data stored in MongoDB", 
            "db_id": str(result.inserted_id)
        }
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Database insertion failed")