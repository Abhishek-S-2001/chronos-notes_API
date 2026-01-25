import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

load_dotenv()

# Configuration
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "chronos_db"

class Database:
    client: MongoClient = None

db_instance = Database()

def connect_db():
    """Establishes connection to MongoDB"""
    try:
        db_instance.client = MongoClient(MONGO_URI)
        # Quick ping to verify
        db_instance.client.admin.command('ping')
        print("✅ MongoDB Connected Successfully")
    except ConnectionFailure as e:
        print(f"❌ MongoDB Connection Failed: {e}")

def close_db():
    """Closes connection"""
    if db_instance.client:
        db_instance.client.close()
        print("🛑 MongoDB Connection Closed")

def get_db():
    """Dependency for Routers to access the database"""
    if db_instance.client is None:
        # Try reconnecting if connection dropped
        connect_db()
    return db_instance.client[DB_NAME]