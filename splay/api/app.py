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

Automa Execution Flow (Option A):
    1. POST /photo processes the image
    2. If confidence is high (requires_confirmation=false):
       - Automa turn is computed immediately
       - Response includes automa_instructions
    3. If corrections needed (requires_confirmation=true):
       - POST /corrections must be called
       - After all corrections resolved, automa runs automatically
       - Response includes automa_instructions

All responses are JSON with explicit Pydantic schemas.
Photos are multipart/form-data.
"""

from typing import Annotated, Optional, Union
import json
import os

# Environment configuration
SPLAY_ENV = os.getenv("SPLAY_ENV", "development")
SPLAY_CACHE_DIR = os.getenv("SPLAY_CACHE_DIR", None)
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")


def create_app(service=None):
    """
    Create the FastAPI application.

    Args:
        service: Optional APIService instance (creates new if not provided)

    Returns:
        FastAPI application instance
    """
    try:
        from fastapi import (
            FastAPI, HTTPException, UploadFile, File, Form, WebSocket, Body, Query
        )
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import JSONResponse
    except ImportError:
        raise ImportError(
            "FastAPI not installed. Install with: pip install fastapi uvicorn python-multipart"
        )

    from .service import APIService
    from .schemas import (
        # Request models
        CompileRequest,
        CreateSessionRequest,
        PlayerHints,
        CorrectionsRequest,
        Correction,
        # Response models
        CompileResponse,
        SessionResponse,
        GameStateResponse,
        VisionStateProposal,
        InstructionsResponse,
        CorrectionsResponse,
        ErrorResponse,
        SessionListResponse,
        EndSessionResponse,
        HealthResponse,
        # Enums
        ErrorCode,
        SessionStatus,
        ConfidenceLevel,
        # Nested models
        PlayerInfo,
        ZoneInfo,
        CardInfo,
        QuestionInfo,
        InstructionInfo,
        DetectedPlayer,
        DetectedZone,
        DetectedCard,
        UncertaintyInfo,
    )

    app = FastAPI(
        title="Splay Engine API",
        description="""
Board Game Automa Engine - Photo-driven gameplay with AI opponents.

## Automa Execution Flow

After uploading a photo via `POST /photo`:

1. **High confidence** (`requires_confirmation=false`):
   - Automa turn is computed immediately
   - Response includes `automa_instructions` to execute

2. **Low confidence** (`requires_confirmation=true`):
   - Call `POST /corrections` with answers
   - After corrections, automa runs automatically
   - Response includes `automa_instructions`

## Error Codes

| Code | Description |
|------|-------------|
| `PHOTO_UNREADABLE` | Photo could not be processed |
| `LOW_CONFIDENCE` | Vision confidence below threshold |
| `INVALID_CORRECTION` | Correction value is invalid |
| `INVALID_SPEC_ID` | Spec ID not found |
| `SESSION_NOT_FOUND` | Session does not exist |
        """,
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # CORS for mobile app
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Service instance
    from ..rule_compiler import RuleCompiler
    rule_compiler = RuleCompiler(cache_dir=SPLAY_CACHE_DIR) if SPLAY_CACHE_DIR else RuleCompiler()
    api_service = service or APIService(rule_compiler=rule_compiler)

    # WebSocket connections
    ws_connections: dict[str, list[WebSocket]] = {}

    # =========================================================================
    # Error helpers
    # =========================================================================

    def make_error_response(
        error_code: ErrorCode,
        message: str,
        status_code: int = 400,
        details: Optional[dict] = None,
    ) -> JSONResponse:
        """Create a standardized error response."""
        return JSONResponse(
            status_code=status_code,
            content=ErrorResponse(
                error=message,
                error_code=error_code,
                details=details,
            ).model_dump(),
        )

    async def broadcast_to_session(session_id: str, message: dict):
        """Broadcast a message to all WebSocket connections for a session."""
        if session_id in ws_connections:
            dead_connections = []
            for ws in ws_connections[session_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    dead_connections.append(ws)
            for ws in dead_connections:
                ws_connections[session_id].remove(ws)

    # =========================================================================
    # Compile Endpoint
    # =========================================================================

    @app.post(
        "/api/v1/compile",
        response_model=CompileResponse,
        responses={400: {"model": ErrorResponse}},
        tags=["Rules"],
        summary="Compile rules text into a GameSpec",
    )
    async def compile_rules(
        rules_text: Annotated[str, Form(description="Full rules text to compile")],
        game_name: Annotated[Optional[str], Form(description="Name for the game")] = None,
        faq_text: Annotated[Optional[str], Form(description="Optional FAQ/errata")] = None,
        force_recompile: Annotated[bool, Form(description="Force recompilation")] = False,
    ) -> CompileResponse:
        """
        Compile rules text into a GameSpec.

        Returns a `spec_id` that can be used to create game sessions.
        Results are cached by rules hash.
        """
        from .models import CompileRulesRequest
        request = CompileRulesRequest(
            rules_text=rules_text,
            game_name=game_name,
            faq_text=faq_text,
            force_recompile=force_recompile,
        )
        response = api_service.compile_rules(request)

        return CompileResponse(
            success=response.success,
            status=response.status.value,
            spec_id=response.spec_id,
            rules_hash=response.rules_hash,
            game_name=response.game_name,
            player_count_min=response.player_count[0] if response.player_count else None,
            player_count_max=response.player_count[1] if response.player_count else None,
            card_count=response.card_count,
            warnings=response.warnings,
            errors=response.errors,
        )

    # =========================================================================
    # Session Endpoints
    # =========================================================================

    @app.post(
        "/api/v1/sessions",
        response_model=SessionResponse,
        responses={
            400: {"model": ErrorResponse, "description": "Invalid spec_id or parameters"},
        },
        tags=["Sessions"],
        summary="Create a new game session",
    )
    async def create_session(
        game_type: Annotated[str, Form(description="Built-in game type")] = "innovation",
        num_automas: Annotated[int, Form(description="Number of AI opponents (1-3)", ge=1, le=3)] = 1,
        human_player_name: Annotated[str, Form(description="Display name for human")] = "Player",
        spec_id: Annotated[Optional[str], Form(description="Use a compiled spec")] = None,
    ) -> SessionResponse:
        """
        Create a new game session.

        Use `game_type=innovation` for the built-in Innovation game,
        or provide a `spec_id` from a previous compilation.
        """
        from .models import CreateSessionRequest as LegacyCreateRequest
        request = LegacyCreateRequest(
            game_type=game_type,
            num_automas=num_automas,
            human_player_name=human_player_name,
            spec_id=spec_id,
        )

        try:
            response = api_service.create_session(request)
        except ValueError as e:
            error_msg = str(e)
            if "spec" in error_msg.lower():
                return make_error_response(ErrorCode.INVALID_SPEC_ID, error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        return _convert_session_response(response)

    @app.get(
        "/api/v1/sessions/{session_id}",
        response_model=SessionResponse,
        responses={404: {"model": ErrorResponse}},
        tags=["Sessions"],
        summary="Get session status",
    )
    async def get_session(session_id: str) -> Union[SessionResponse, JSONResponse]:
        """Get the current status of a game session."""
        response = api_service.get_session(session_id)
        if hasattr(response, "error"):
            return make_error_response(
                ErrorCode.SESSION_NOT_FOUND,
                response.error,
                status_code=404,
            )
        return _convert_session_response(response)

    @app.delete(
        "/api/v1/sessions/{session_id}",
        response_model=EndSessionResponse,
        tags=["Sessions"],
        summary="End a game session",
    )
    async def end_session(
        session_id: str,
        reason: Annotated[str, Query(description="Reason for ending")] = "user_ended",
    ) -> EndSessionResponse:
        """End a game session and release resources."""
        success = api_service.end_session(session_id, reason)
        return EndSessionResponse(success=success, session_id=session_id)

    @app.get(
        "/api/v1/sessions",
        response_model=SessionListResponse,
        tags=["Sessions"],
        summary="List active sessions",
    )
    async def list_sessions() -> SessionListResponse:
        """List all active session IDs."""
        sessions = api_service.list_sessions()
        return SessionListResponse(sessions=sessions, count=len(sessions))

    # =========================================================================
    # Photo Processing Endpoint
    # =========================================================================

    @app.post(
        "/api/v1/sessions/{session_id}/photo",
        response_model=VisionStateProposal,
        responses={
            400: {"model": ErrorResponse, "description": "Photo unreadable"},
            404: {"model": ErrorResponse, "description": "Session not found"},
        },
        tags=["Game Loop"],
        summary="Upload a photo of the game table",
    )
    async def upload_photo(
        session_id: str,
        photo: Annotated[UploadFile, File(description="Photo of the game table")],
        player_hints: Annotated[
            Optional[str],
            Form(description="JSON: {\"player_id\": \"position\"} where position is top/bottom/left/right")
        ] = None,
    ) -> Union[VisionStateProposal, JSONResponse]:
        """
        Upload a photo of the game table for vision processing.

        **Automa Flow:**
        - If `requires_confirmation=false`: automa instructions are included
        - If `requires_confirmation=true`: call `/corrections` first

        **Player Hints Format:**
        ```json
        {"human": "bottom", "bot_1": "top"}
        ```
        """
        # Parse player hints
        hints_obj = None
        if player_hints:
            try:
                hints_obj = json.loads(player_hints)
            except json.JSONDecodeError:
                return make_error_response(
                    ErrorCode.VALIDATION_ERROR,
                    "Invalid player_hints JSON format",
                )

        # Check session exists
        session = api_service.session_manager.get_session(session_id)
        if not session:
            return make_error_response(
                ErrorCode.SESSION_NOT_FOUND,
                f"Session {session_id} not found",
                status_code=404,
            )

        # Read image data
        try:
            image_data = await photo.read()
            if len(image_data) == 0:
                return make_error_response(
                    ErrorCode.PHOTO_UNREADABLE,
                    "Empty photo file",
                )
        except Exception as e:
            return make_error_response(
                ErrorCode.PHOTO_UNREADABLE,
                f"Failed to read photo: {str(e)}",
            )

        # Process photo
        from .models import UploadPhotoRequest
        metadata = UploadPhotoRequest(
            session_id=session_id,
            player_hints=hints_obj,
        )

        result = api_service.process_photo(session_id, image_data, metadata)

        # Convert to VisionStateProposal
        proposal = _convert_photo_result_to_proposal(session_id, result)

        # Broadcast update via WebSocket
        await broadcast_to_session(session_id, {
            "type": "state_update",
            "payload": proposal.model_dump(),
        })

        return proposal

    # =========================================================================
    # Corrections Endpoint
    # =========================================================================

    @app.post(
        "/api/v1/sessions/{session_id}/corrections",
        response_model=CorrectionsResponse,
        responses={
            400: {"model": ErrorResponse, "description": "Invalid correction"},
            404: {"model": ErrorResponse, "description": "Session not found"},
        },
        tags=["Game Loop"],
        summary="Submit corrections for ambiguous detections",
    )
    async def submit_corrections(
        session_id: str,
        body: CorrectionsRequest,
    ) -> Union[CorrectionsResponse, JSONResponse]:
        """
        Submit corrections for uncertainties from vision processing.

        After all corrections are resolved, the automa turn is computed automatically
        and `automa_instructions` are included in the response.

        **Request Body:**
        ```json
        {
            "corrections": [
                {"question_id": "q1", "value": "archery"},
                {"question_id": "q2", "value": 3}
            ],
            "skip_remaining": false
        }
        ```
        """
        # Check session exists
        session = api_service.session_manager.get_session(session_id)
        if not session:
            return make_error_response(
                ErrorCode.SESSION_NOT_FOUND,
                f"Session {session_id} not found",
                status_code=404,
            )

        # Convert corrections list to dict
        corrections_dict = {c.question_id: c.value for c in body.corrections}

        # Validate corrections (basic validation)
        game_loop = api_service._game_loops.get(session_id)
        if game_loop and game_loop._pending_questions:
            valid_question_ids = {q.get("id") for q in game_loop._pending_questions}
            for correction in body.corrections:
                if correction.question_id not in valid_question_ids:
                    return make_error_response(
                        ErrorCode.INVALID_CORRECTION,
                        f"Unknown question_id: {correction.question_id}",
                        details={"valid_ids": list(valid_question_ids)},
                    )

        # Submit corrections
        from .models import SubmitCorrectionRequest
        request = SubmitCorrectionRequest(
            session_id=session_id,
            corrections=corrections_dict,
            skip_remaining=body.skip_remaining,
        )
        result = api_service.submit_corrections(request)

        # Convert response
        response = CorrectionsResponse(
            session_id=session_id,
            success=result.success,
            status=result.status.value,
            remaining_questions=[
                QuestionInfo(
                    question_id=q.question_id,
                    question_type=q.question_type.value,
                    question_text=q.question_text,
                    options=q.options,
                    detected_value=q.detected_value,
                    is_required=q.is_required,
                    hint=q.hint,
                )
                for q in result.remaining_questions
            ],
            automa_executed=len(result.automa_actions) > 0,
            automa_actions=result.automa_actions,
            automa_instructions=[
                InstructionInfo(
                    instruction_id=inst.instruction_id,
                    text=inst.text,
                    action_type=inst.action_type,
                    source_zone=inst.source_zone,
                    target_zone=inst.target_zone,
                    is_complete=inst.is_complete,
                )
                for inst in result.instructions
            ],
            game_state=_convert_game_state(result.game_state) if result.game_state else None,
        )

        # Broadcast update
        await broadcast_to_session(session_id, {
            "type": "state_update",
            "payload": response.model_dump(),
        })

        return response

    # =========================================================================
    # State & Instructions Endpoints
    # =========================================================================

    @app.get(
        "/api/v1/sessions/{session_id}/state",
        response_model=GameStateResponse,
        responses={404: {"model": ErrorResponse}},
        tags=["Game Loop"],
        summary="Get current game state",
    )
    async def get_game_state(session_id: str) -> Union[GameStateResponse, JSONResponse]:
        """Get the complete current game state for display."""
        response = api_service.get_game_state(session_id)
        if hasattr(response, "error"):
            return make_error_response(
                ErrorCode.SESSION_NOT_FOUND,
                response.error,
                status_code=404,
            )
        return _convert_game_state(response)

    @app.get(
        "/api/v1/sessions/{session_id}/instructions",
        response_model=InstructionsResponse,
        responses={404: {"model": ErrorResponse}},
        tags=["Game Loop"],
        summary="Get pending instructions for human player",
    )
    async def get_instructions(session_id: str) -> Union[InstructionsResponse, JSONResponse]:
        """
        Get pending instructions that the human player should execute physically.

        These are the actions the automa has decided to take.
        """
        response = api_service.get_instructions(session_id)
        if hasattr(response, "error"):
            return make_error_response(
                ErrorCode.SESSION_NOT_FOUND,
                response.error,
                status_code=404,
            )

        return InstructionsResponse(
            session_id=session_id,
            instructions=[
                InstructionInfo(
                    instruction_id=inst.instruction_id,
                    text=inst.text,
                    action_type=inst.action_type,
                    source_zone=inst.source_zone,
                    target_zone=inst.target_zone,
                    is_complete=inst.is_complete,
                )
                for inst in response.instructions
            ],
            automa_player=response.automa_player,
            summary=response.summary,
            next_action=response.next_action,
        )

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

        if session_id not in ws_connections:
            ws_connections[session_id] = []
        ws_connections[session_id].append(websocket)

        try:
            # Send initial state
            response = api_service.get_game_state(session_id)
            if not hasattr(response, "error"):
                await websocket.send_json({
                    "type": "state_update",
                    "payload": _convert_game_state(response).model_dump(),
                })

            # Listen for messages
            while True:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    if message.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": "Invalid JSON"},
                    })

        except Exception:
            pass
        finally:
            if session_id in ws_connections:
                if websocket in ws_connections[session_id]:
                    ws_connections[session_id].remove(websocket)

    # =========================================================================
    # Health Check
    # =========================================================================

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["System"],
        summary="Health check",
    )
    async def health_check() -> HealthResponse:
        """Health check endpoint for load balancers."""
        return HealthResponse(
            status="healthy",
            service="splay-engine",
            version="1.0.0",
        )

    @app.get("/", tags=["System"])
    async def root():
        """Root endpoint with API info."""
        return {
            "name": "Splay Engine API",
            "version": "1.0.0",
            "docs": "/api/docs",
            "health": "/health",
        }

    # =========================================================================
    # Conversion Helpers
    # =========================================================================

    def _convert_session_response(response) -> SessionResponse:
        """Convert legacy SessionResponse to Pydantic model."""
        return SessionResponse(
            session_id=response.session_id,
            status=response.status.value,
            game_name=response.game_name,
            players=[
                PlayerInfo(
                    player_id=p.player_id,
                    name=p.name,
                    is_human=p.is_human,
                    is_current_turn=p.is_current_turn,
                    score=p.score,
                    achievement_count=p.achievement_count,
                    zones=[
                        ZoneInfo(
                            zone_id=z.zone_id,
                            zone_type=z.zone_type,
                            card_count=z.card_count,
                            top_card=CardInfo(
                                card_id=z.top_card.card_id,
                                name=z.top_card.name,
                                age=z.top_card.age,
                                color=z.top_card.color,
                            ) if z.top_card else None,
                            splay_direction=z.splay_direction,
                        )
                        for z in p.zones
                    ],
                )
                for p in response.players
            ],
            current_turn_player_id=response.current_turn_player_id,
            turn_number=response.turn_number,
            created_at=response.created_at,
        )

    def _convert_game_state(response) -> GameStateResponse:
        """Convert legacy GameStateResponse to Pydantic model."""
        return GameStateResponse(
            session_id=response.session_id,
            status=response.status.value,
            turn_number=response.turn_number,
            players=[
                PlayerInfo(
                    player_id=p.player_id,
                    name=p.name,
                    is_human=p.is_human,
                    is_current_turn=p.is_current_turn,
                    score=p.score,
                    achievement_count=p.achievement_count,
                    zones=[
                        ZoneInfo(
                            zone_id=z.zone_id,
                            zone_type=z.zone_type,
                            card_count=z.card_count,
                            top_card=CardInfo(
                                card_id=z.top_card.card_id,
                                name=z.top_card.name,
                                age=z.top_card.age,
                                color=z.top_card.color,
                            ) if z.top_card else None,
                            splay_direction=z.splay_direction,
                        )
                        for z in p.zones
                    ],
                )
                for p in response.players
            ],
            current_turn_player_id=response.current_turn_player_id,
            available_achievements=[
                CardInfo(
                    card_id=a.card_id,
                    name=a.name,
                    age=a.age,
                    color=a.color,
                )
                for a in response.available_achievements
            ],
            deck_sizes=response.deck_sizes,
            your_achievements=response.your_achievements,
            achievements_to_win=response.achievements_to_win,
            winner=PlayerInfo(
                player_id=response.winner.player_id,
                name=response.winner.name,
                is_human=response.winner.is_human,
                is_current_turn=response.winner.is_current_turn,
                score=response.winner.score,
                achievement_count=response.winner.achievement_count,
            ) if response.winner else None,
            game_over_reason=response.game_over_reason,
        )

    def _convert_photo_result_to_proposal(session_id: str, result) -> VisionStateProposal:
        """Convert PhotoResultResponse to VisionStateProposal."""
        import time
        import uuid

        # Determine if confirmation is required
        has_questions = len(result.questions) > 0
        confidence_threshold = 0.7
        requires_confirmation = has_questions or result.confidence < confidence_threshold

        # Build detected players from game state if available
        detected_players = []
        if result.game_state:
            for player in result.game_state.players:
                board_piles = {}
                for zone in player.zones:
                    if zone.zone_type == "board_pile":
                        color = zone.zone_id.split("_")[-1]
                        board_piles[color] = DetectedZone(
                            zone_type="board_pile",
                            player_id=player.player_id,
                            color=color,
                            card_count=zone.card_count,
                            splay_direction=zone.splay_direction or "unknown",
                            cards=[
                                DetectedCard(
                                    detected_name=zone.top_card.name,
                                    detected_age=zone.top_card.age,
                                    detected_color=zone.top_card.color,
                                    matched_card_id=zone.top_card.card_id,
                                    confidence="high",
                                )
                            ] if zone.top_card else [],
                        )

                detected_players.append(DetectedPlayer(
                    player_id=player.player_id,
                    board_piles=board_piles,
                ))

        # Build uncertainties from questions
        uncertainties = [
            UncertaintyInfo(
                zone_id=q.question_id,
                zone_type="unknown",
                uncertainty_type=q.question_type.value if hasattr(q.question_type, 'value') else str(q.question_type),
                question=q.question_text,
                detected_value=q.detected_value,
                alternatives=[opt.get("label", opt) for opt in q.options] if q.options else [],
            )
            for q in result.questions
        ]

        return VisionStateProposal(
            proposal_id=str(uuid.uuid4()),
            session_id=session_id,
            timestamp=time.time(),
            confidence_score=result.confidence,
            confidence_level=(
                "high" if result.confidence >= 0.9 else
                "medium" if result.confidence >= 0.6 else
                "low" if result.confidence >= 0.3 else
                "uncertain"
            ),
            players=detected_players,
            deck_sizes=result.game_state.deck_sizes if result.game_state else {},
            uncertainties=uncertainties,
            requires_confirmation=requires_confirmation,
            automa_executed=not requires_confirmation and len(result.automa_actions) > 0,
            automa_actions=result.automa_actions if not requires_confirmation else [],
            automa_instructions=[
                InstructionInfo(
                    instruction_id=inst.instruction_id,
                    text=inst.text,
                    action_type=inst.action_type,
                    source_zone=inst.source_zone,
                    target_zone=inst.target_zone,
                    is_complete=inst.is_complete,
                )
                for inst in result.instructions
            ] if not requires_confirmation else [],
            game_state=_convert_game_state(result.game_state) if result.game_state else None,
            validation_errors=result.errors,
            validation_warnings=result.warnings,
        )

    return app


# For running directly: uvicorn splay.api.app:app
app = None
try:
    app = create_app()
except ImportError:
    # FastAPI not installed
    pass
