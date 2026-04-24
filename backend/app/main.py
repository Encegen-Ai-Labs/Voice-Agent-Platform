from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
import app.models  
from app.api import auth
from app.api import agents
from app.api import calls
from app.api import websocket

app = FastAPI(
    title="Voice-Agent-Platform",
    description="AI Voice Agent Platform",
    version="0.1.0"
)

app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(calls.router)
app.include_router(websocket.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}

@app.get("/")
async def root():
    return {"message": "Voice-Agent-Platform API is running", "docs": "/docs"}