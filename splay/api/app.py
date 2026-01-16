"""
FastAPI Application - REST API for mobile app.

Endpoints:
    POST   /api/v1/compile              Compile rules to GameSpec
    POST   /api/v1/sessions             Create game session
    GET    /api/v1/sessions/{id}        Get session status
    DELETE /api/v1/sessions/{id}        End session
    POST   /api/v1/sessions/{id}/photo  Upload photo
    POST   /api/v1/sessions/{id}/corrections  Submit corrections
    GET    /api/v1/sessions/{id}/state  Get game state
    GET    /api/v1/sessions/{id}/instructions  Get pending instructions
    WS     /api/v1/sessions/{id}/ws     WebSocket for real-time updates

All responses are JSON. Photos are multipart/form-data.

Deployment:
    # Local
    uvicorn splay.api.app:app --reload

    # Production (Render)
    uvicorn splay.api.app:app --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations
from typing import Any
from dataclasses import asdict
import json
import os

# Environment configuration
SPLAY_ENV = os.getenv("SPLAY_ENV", "development")
SPLAY_CACHE_DIR = os.getenv("SPLAY_CACHE_DIR", None)
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# Framework-agnostic interface
# The actual FastAPI app is created in create_app()


def create_app(service=None):
    """
    Create the FastAPI application.

    Args:
        service: Optional APIService instance (creates new if not provided)

    Returns:
        FastAPI application instance
    """
    try:
        from fastapi import FastAPI, HTTPException, UploadFile, File, Form, WebSocket
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import JSONResponse
    except ImportError:
        raise ImportError(
            "FastAPI not installed. Install with: pip install fastapi uvicorn python-multipart"
        )

    from .service import APIService
    from .models import (
        CompileRulesRequest,
        CreateSessionRequest,
        SubmitCorrectionRequest,
        UploadPhotoRequest,
        WSMessage,
        WSMessageType,
    )

    app = FastAPI(
        title="Splay Engine API",
        description="Board Game Automa Engine - Photo-driven gameplay with AI opponents",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # CORS for mobile app
    # Set ALLOWED_ORIGINS env var for production (comma-separated)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Service instance with optional cache directory
    from ..rule_compiler import RuleCompiler
    rule_compiler = RuleCompiler(cache_dir=SPLAY_CACHE_DIR) if SPLAY_CACHE_DIR else RuleCompiler()
    api_service = service or APIService(rule_compiler=rule_compiler)

    # WebSocket connections
    ws_connections: dict[str, list[WebSocket]] = {}

    # =========================================================================
    # Helper functions
    # =========================================================================

    def to_json(obj) -> dict:
        """Convert dataclass to JSON-serializable dict."""
        if hasattr(obj, "__dataclass_fields__"):
            result = {}
            for field_name in obj.__dataclass_fields__:
                value = getattr(obj, field_name)
                result[field_name] = to_json(value)
            return result
        elif isinstance(obj, list):
            return [to_json(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: to_json(v) for k, v in obj.items()}
        elif hasattr(obj, "value"):  # Enum
            return obj.value
        elif isinstance(obj, tuple):
            return list(obj)
        else:
            return obj

    async def broadcast_to_session(session_id: str, message: dict):
        """Broadcast a message to all WebSocket connections for a session."""
        if session_id in ws_connections:
            dead_connections = []
            for ws in ws_connections[session_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    dead_connections.append(ws)

            # Clean up dead connections
            for ws in dead_connections:
                ws_connections[session_id].remove(ws)

    # =========================================================================
    # REST Endpoints
    # =========================================================================

    @app.post("/api/v1/compile")
    async def compile_rules(
        rules_text: str = Form(...),
        game_name: str = Form(None),
        faq_text: str = Form(None),
        force_recompile: bool = Form(False),
    ):
        """Compile rules text into a GameSpec."""
        request = CompileRulesRequest(
            rules_text=rules_text,
            game_name=game_name,
            faq_text=faq_text,
            force_recompile=force_recompile,
        )
        response = api_service.compile_rules(request)
        return JSONResponse(content=to_json(response))

    @app.post("/api/v1/sessions")
    async def create_session(
        game_type: str = Form("innovation"),
        num_automas: int = Form(1),
        human_player_name: str = Form("Player"),
        spec_id: str = Form(None),
    ):
        """Create a new game session."""
        request = CreateSessionRequest(
            game_type=game_type,
            num_automas=num_automas,
            human_player_name=human_player_name,
            spec_id=spec_id,
        )
        try:
            response = api_service.create_session(request)
            return JSONResponse(content=to_json(response))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/v1/sessions/{session_id}")
    async def get_session(session_id: str):
        """Get session status."""
        response = api_service.get_session(session_id)
        if hasattr(response, "error"):
            raise HTTPException(status_code=404, detail=response.error)
        return JSONResponse(content=to_json(response))

    @app.delete("/api/v1/sessions/{session_id}")
    async def end_session(session_id: str, reason: str = "user_ended"):
        """End a game session."""
        success = api_service.end_session(session_id, reason)
        return {"success": success, "session_id": session_id}

    @app.post("/api/v1/sessions/{session_id}/photo")
    async def upload_photo(
        session_id: str,
        photo: UploadFile = File(...),
        player_hints: str = Form(None),  # JSON string
    ):
        """
        Upload a photo of the game table.

        The photo should be a clear image of the entire table.
        Returns detected state and any questions needing answers.
        """
        # Read image data
        image_data = await photo.read()

        # Parse hints if provided
        hints = None
        if player_hints:
            try:
                hints = json.loads(player_hints)
            except json.JSONDecodeError:
                pass

        metadata = UploadPhotoRequest(
            session_id=session_id,
            player_hints=hints,
        )

        response = api_service.process_photo(session_id, image_data, metadata)

        # Broadcast state update via WebSocket
        await broadcast_to_session(session_id, {
            "type": WSMessageType.STATE_UPDATE.value,
            "payload": to_json(response),
        })

        return JSONResponse(content=to_json(response))

    @app.post("/api/v1/sessions/{session_id}/corrections")
    async def submit_corrections(
        session_id: str,
        corrections: str = Form(...),  # JSON string
    ):
        """Submit corrections for ambiguous detections."""
        try:
            corrections_dict = json.loads(corrections)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid corrections JSON")

        request = SubmitCorrectionRequest(
            session_id=session_id,
            corrections=corrections_dict,
        )
        response = api_service.submit_corrections(request)

        # Broadcast update
        await broadcast_to_session(session_id, {
            "type": WSMessageType.STATE_UPDATE.value,
            "payload": to_json(response),
        })

        return JSONResponse(content=to_json(response))

    @app.get("/api/v1/sessions/{session_id}/state")
    async def get_game_state(session_id: str):
        """Get current game state."""
        response = api_service.get_game_state(session_id)
        if hasattr(response, "error"):
            raise HTTPException(status_code=404, detail=response.error)
        return JSONResponse(content=to_json(response))

    @app.get("/api/v1/sessions/{session_id}/instructions")
    async def get_instructions(session_id: str):
        """Get pending instructions for the human player."""
        response = api_service.get_instructions(session_id)
        if hasattr(response, "error"):
            raise HTTPException(status_code=404, detail=response.error)
        return JSONResponse(content=to_json(response))

    @app.get("/api/v1/sessions")
    async def list_sessions():
        """List active sessions."""
        sessions = api_service.list_sessions()
        return {"sessions": sessions, "count": len(sessions)}

    # =========================================================================
    # WebSocket Endpoint
    # =========================================================================

    @app.websocket("/api/v1/sessions/{session_id}/ws")
    async def websocket_endpoint(websocket: WebSocket, session_id: str):
        """
        WebSocket for real-time updates.

        Messages from server:
        - state_update: Game state changed
        - instructions: New instructions for human
        - automa_thinking: Bot is processing
        - automa_action: Bot took an action
        - game_over: Game ended
        - error: Error occurred

        Messages from client:
        - ping: Keep-alive
        """
        await websocket.accept()

        # Add to connections
        if session_id not in ws_connections:
            ws_connections[session_id] = []
        ws_connections[session_id].append(websocket)

        try:
            # Send initial state
            response = api_service.get_game_state(session_id)
            if not hasattr(response, "error"):
                await websocket.send_json({
                    "type": WSMessageType.STATE_UPDATE.value,
                    "payload": to_json(response),
                })

            # Listen for messages
            while True:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    msg_type = message.get("type")

                    if msg_type == "ping":
                        await websocket.send_json({"type": "pong"})

                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": "Invalid JSON"},
                    })

        except Exception:
            pass
        finally:
            # Remove from connections
            if session_id in ws_connections:
                if websocket in ws_connections[session_id]:
                    ws_connections[session_id].remove(websocket)

    # =========================================================================
    # Health check
    # =========================================================================

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "splay-engine",
            "version": "1.0.0",
        }

    @app.get("/")
    async def root():
        """Root endpoint with API info."""
        return {
            "name": "Splay Engine API",
            "version": "1.0.0",
            "docs": "/api/docs",
            "health": "/health",
        }

    return app


# For running directly: uvicorn splay.api.app:app
app = None
try:
    app = create_app()
except ImportError:
    # FastAPI not installed
    pass
