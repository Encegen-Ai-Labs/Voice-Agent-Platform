from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
import app.models  
from app.api import auth
from app.api import agents
from app.api import calls
from app.api import websocket
from app.api import telephony
from app.api import workspaces
from app.api import phone_numbers
from app.api import api_keys
from app.api import knowledge_base
from app.api import web_voice
from app.api import voice

from app.core.rate_limit import limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Voice-Agent-Platform",
    description="AI Voice Agent Platform",
    version="0.1.0"
)

app.state.limiter = limiter

app.add_middleware(SlowAPIMiddleware)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):

    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation failed",
            "errors": exc.errors()
        }
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(
    request: Request,
    exc: SQLAlchemyError
):

    logger.exception(
        "Database error: %s",
        exc
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Database operation failed"
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception
):

    logger.exception(
        "Unhandled exception: %s",
        exc
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error"
        }
    )

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(
    request: Request,
    exc: RateLimitExceeded
):

    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded"
        }
    )

app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(calls.router)
app.include_router(websocket.router)
app.include_router(telephony.router)
app.include_router(workspaces.router)
app.include_router(phone_numbers.router)
app.include_router(api_keys.router)
app.include_router(knowledge_base.router)
app.include_router(web_voice.router)
app.include_router(voice.router)

app.add_middleware(
    CORSMiddleware,
     allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
    ],

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