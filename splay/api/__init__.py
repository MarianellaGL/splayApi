"""
API Module - Mobile app interface.

Exposes the engine via REST API for mobile consumption.
The mobile app:
1. Uploads rules to compile
2. Creates game sessions
3. Uploads photos of the table
4. Receives state updates and instructions
5. Submits corrections when needed

All state is session-scoped. No persistent user accounts required.
"""

from .models import (
    # Requests
    CompileRulesRequest,
    CreateSessionRequest,
    UploadPhotoRequest,
    SubmitCorrectionRequest,
    # Responses
    CompileRulesResponse,
    SessionResponse,
    GameStateResponse,
    PhotoResultResponse,
    InstructionsResponse,
    ErrorResponse,
    # Shared
    PlayerInfo,
    ZoneInfo,
    CardInfo,
    QuestionInfo,
)
from .service import APIService
from .app import create_app

__all__ = [
    # Requests
    "CompileRulesRequest",
    "CreateSessionRequest",
    "UploadPhotoRequest",
    "SubmitCorrectionRequest",
    # Responses
    "CompileRulesResponse",
    "SessionResponse",
    "GameStateResponse",
    "PhotoResultResponse",
    "InstructionsResponse",
    "ErrorResponse",
    # Shared
    "PlayerInfo",
    "ZoneInfo",
    "CardInfo",
    "QuestionInfo",
    # Service
    "APIService",
    "create_app",
]
