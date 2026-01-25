from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database import connect_db, close_db
from app.routers import notes, analytics, users

# --- Lifespan Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    connect_db()
    yield
    close_db()

# --- App Setup ---
app = FastAPI(title="Chronos API", lifespan=lifespan)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow Next.js
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include Routers ---
app.include_router(notes.router)
app.include_router(analytics.router)
app.include_router(users.router)

@app.get("/")
def health_check():
    return {"status": "System Online", "version": "2.0 (Modular)"}