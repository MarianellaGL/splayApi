"""
Tests for API Pydantic schemas.

Validates that:
- Request/response models serialize correctly
- Error codes are properly structured
- VisionStateProposal has all required fields
- Automa flow fields are present
"""

import pytest
from pydantic import ValidationError


class TestPydanticSchemas:
    """Tests for Pydantic schema validation."""

    def test_compile_response_schema(self):
        """CompileResponse has all required fields."""
        from splay.api.schemas import CompileResponse, CompilationStatus

        response = CompileResponse(
            success=True,
            status=CompilationStatus.SUCCESS,
            spec_id="test-spec-123",
            rules_hash="abc123",
            game_name="Test Game",
            player_count_min=2,
            player_count_max=4,
            card_count=105,
            warnings=["Minor issue found"],
            errors=[],
        )

        data = response.model_dump()
        assert data["success"] is True
        assert data["status"] == "success"
        assert data["spec_id"] == "test-spec-123"
        assert data["card_count"] == 105

    def test_session_response_schema(self):
        """SessionResponse has all required fields."""
        from splay.api.schemas import SessionResponse, SessionStatus, PlayerInfo

        response = SessionResponse(
            session_id="session-123",
            status=SessionStatus.ACTIVE,
            game_name="Innovation",
            players=[
                PlayerInfo(
                    player_id="human",
                    name="Player 1",
                    is_human=True,
                    is_current_turn=True,
                    score=5,
                    achievement_count=2,
                ),
                PlayerInfo(
                    player_id="bot_1",
                    name="Bot 1",
                    is_human=False,
                    is_current_turn=False,
                ),
            ],
            current_turn_player_id="human",
            turn_number=5,
            created_at=1234567890.0,
        )

        data = response.model_dump()
        assert data["session_id"] == "session-123"
        assert data["status"] == "active"
        assert len(data["players"]) == 2
        assert data["players"][0]["is_human"] is True
        assert data["api_version"] == "v1"

    def test_vision_state_proposal_schema(self):
        """VisionStateProposal has automa flow fields."""
        from splay.api.schemas import (
            VisionStateProposal,
            ConfidenceLevel,
            DetectedPlayer,
            InstructionInfo,
            UncertaintyInfo,
        )

        # High confidence - automa should run
        proposal = VisionStateProposal(
            proposal_id="prop-123",
            session_id="session-456",
            timestamp=1234567890.0,
            confidence_score=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            players=[
                DetectedPlayer(player_id="human"),
                DetectedPlayer(player_id="bot_1"),
            ],
            deck_sizes={"age_1": 10, "age_2": 10},
            uncertainties=[],
            requires_confirmation=False,
            automa_executed=True,
            automa_actions=["Drew age 1 card", "Melded Archery"],
            automa_instructions=[
                InstructionInfo(
                    instruction_id="inst_1",
                    text="Move top card from Age 1 deck to Bot 1's hand",
                    action_type="draw",
                ),
            ],
        )

        data = proposal.model_dump()
        assert data["requires_confirmation"] is False
        assert data["automa_executed"] is True
        assert len(data["automa_actions"]) == 2
        assert len(data["automa_instructions"]) == 1

    def test_vision_proposal_with_uncertainties(self):
        """VisionStateProposal with corrections needed."""
        from splay.api.schemas import (
            VisionStateProposal,
            ConfidenceLevel,
            UncertaintyInfo,
        )

        proposal = VisionStateProposal(
            proposal_id="prop-789",
            session_id="session-456",
            timestamp=1234567890.0,
            confidence_score=0.45,
            confidence_level=ConfidenceLevel.LOW,
            uncertainties=[
                UncertaintyInfo(
                    zone_id="q1",
                    zone_type="board_pile",
                    uncertainty_type="card_identity",
                    question="What card is on top of the blue pile?",
                    alternatives=["Archery", "Writing", "Agriculture"],
                ),
            ],
            requires_confirmation=True,
            automa_executed=False,
            automa_actions=[],
            automa_instructions=[],
        )

        data = proposal.model_dump()
        assert data["requires_confirmation"] is True
        assert data["automa_executed"] is False
        assert len(data["uncertainties"]) == 1
        assert data["uncertainties"][0]["question"].startswith("What card")

    def test_error_response_schema(self):
        """ErrorResponse has structured error codes."""
        from splay.api.schemas import ErrorResponse, ErrorCode

        error = ErrorResponse(
            error="Session not found",
            error_code=ErrorCode.SESSION_NOT_FOUND,
            details={"session_id": "bad-id"},
        )

        data = error.model_dump()
        assert data["error"] == "Session not found"
        assert data["error_code"] == "SESSION_NOT_FOUND"
        assert data["details"]["session_id"] == "bad-id"
        assert data["api_version"] == "v1"

    def test_corrections_request_schema(self):
        """CorrectionsRequest has typed corrections."""
        from splay.api.schemas import CorrectionsRequest, Correction

        request = CorrectionsRequest(
            corrections=[
                Correction(question_id="q1", value="archery"),
                Correction(question_id="q2", value=3),
                Correction(question_id="q3", value=True),
            ],
            skip_remaining=False,
        )

        data = request.model_dump()
        assert len(data["corrections"]) == 3
        assert data["corrections"][0]["question_id"] == "q1"
        assert data["corrections"][0]["value"] == "archery"
        assert data["corrections"][1]["value"] == 3
        assert data["skip_remaining"] is False

    def test_corrections_request_validation(self):
        """CorrectionsRequest validates required fields."""
        from splay.api.schemas import CorrectionsRequest, Correction

        # Missing corrections should fail
        with pytest.raises(ValidationError):
            CorrectionsRequest()

        # Empty corrections is valid
        request = CorrectionsRequest(corrections=[])
        assert len(request.corrections) == 0

    def test_game_state_response_schema(self):
        """GameStateResponse has complete game state."""
        from splay.api.schemas import (
            GameStateResponse,
            SessionStatus,
            PlayerInfo,
            CardInfo,
            ZoneInfo,
        )

        response = GameStateResponse(
            session_id="session-123",
            status=SessionStatus.YOUR_TURN,
            turn_number=10,
            players=[
                PlayerInfo(
                    player_id="human",
                    name="Player",
                    is_human=True,
                    is_current_turn=True,
                    score=15,
                    achievement_count=3,
                    zones=[
                        ZoneInfo(
                            zone_id="human_board_blue",
                            zone_type="board_pile",
                            card_count=3,
                            top_card=CardInfo(
                                card_id="writing",
                                name="Writing",
                                age=1,
                                color="blue",
                            ),
                            splay_direction="right",
                        ),
                    ],
                ),
            ],
            available_achievements=[
                CardInfo(card_id="monument", name="Monument", age=1),
            ],
            deck_sizes={"age_1": 8, "age_2": 10},
            your_achievements=3,
            achievements_to_win=6,
        )

        data = response.model_dump()
        assert data["turn_number"] == 10
        assert data["your_achievements"] == 3
        assert data["achievements_to_win"] == 6
        assert len(data["players"]) == 1
        assert data["players"][0]["zones"][0]["splay_direction"] == "right"

    def test_instructions_response_schema(self):
        """InstructionsResponse has all automa action fields."""
        from splay.api.schemas import InstructionsResponse, InstructionInfo

        response = InstructionsResponse(
            session_id="session-123",
            instructions=[
                InstructionInfo(
                    instruction_id="inst_1",
                    text="Draw a card from Age 2 deck for Bot 1",
                    action_type="draw",
                    source_zone="deck_age_2",
                    target_zone="bot_1_hand",
                ),
                InstructionInfo(
                    instruction_id="inst_2",
                    text="Meld Astronomy from Bot 1's hand",
                    action_type="meld",
                    source_zone="bot_1_hand",
                    target_zone="bot_1_board_purple",
                ),
            ],
            automa_player="bot_1",
            summary="Bot 1 drew a card and melded Astronomy",
            next_action="take_photo",
        )

        data = response.model_dump()
        assert len(data["instructions"]) == 2
        assert data["instructions"][0]["action_type"] == "draw"
        assert data["automa_player"] == "bot_1"
        assert data["next_action"] == "take_photo"


class TestErrorCodes:
    """Tests for error code coverage."""

    def test_all_error_codes_defined(self):
        """All required error codes are defined."""
        from splay.api.schemas import ErrorCode

        required_codes = [
            "PHOTO_UNREADABLE",
            "LOW_CONFIDENCE",
            "INVALID_CORRECTION",
            "INVALID_SPEC_ID",
            "SESSION_NOT_FOUND",
        ]

        for code in required_codes:
            assert hasattr(ErrorCode, code), f"Missing error code: {code}"
            assert ErrorCode[code].value == code

    def test_error_code_values_are_strings(self):
        """Error codes are string enums for JSON serialization."""
        from splay.api.schemas import ErrorCode

        for code in ErrorCode:
            assert isinstance(code.value, str)
            # Error codes should be UPPER_SNAKE_CASE
            assert code.value == code.value.upper()


class TestOpenAPISchema:
    """Tests for OpenAPI schema generation."""

    def test_openapi_schema_generates(self):
        """OpenAPI schema generates without errors."""
        from splay.api.app import app
        from fastapi.openapi.utils import get_openapi

        schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )

        assert "paths" in schema
        assert "components" in schema
        assert "schemas" in schema["components"]

    def test_response_models_in_schema(self):
        """Response models appear in OpenAPI schema."""
        from splay.api.app import app
        from fastapi.openapi.utils import get_openapi

        schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )

        schemas = schema["components"]["schemas"]

        required_schemas = [
            "CompileResponse",
            "SessionResponse",
            "GameStateResponse",
            "VisionStateProposal",
            "InstructionsResponse",
            "CorrectionsResponse",
            "ErrorResponse",
        ]

        for name in required_schemas:
            assert name in schemas, f"Missing schema: {name}"

    def test_endpoints_have_response_models(self):
        """All main endpoints specify response models."""
        from splay.api.app import app
        from fastapi.openapi.utils import get_openapi

        schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )

        # Check key endpoints have 200 responses with schemas
        paths = schema["paths"]

        # POST /api/v1/sessions should return SessionResponse
        assert "/api/v1/sessions" in paths
        post_session = paths["/api/v1/sessions"]["post"]
        assert "200" in post_session["responses"]

        # GET /api/v1/sessions/{session_id}/state should return GameStateResponse
        assert "/api/v1/sessions/{session_id}/state" in paths
        get_state = paths["/api/v1/sessions/{session_id}/state"]["get"]
        assert "200" in get_state["responses"]

        # POST /api/v1/sessions/{session_id}/photo should return VisionStateProposal
        assert "/api/v1/sessions/{session_id}/photo" in paths
        post_photo = paths["/api/v1/sessions/{session_id}/photo"]["post"]
        assert "200" in post_photo["responses"]
