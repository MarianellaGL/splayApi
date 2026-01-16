"""
Tests for API layer.

Tests:
- API service methods
- Request/response serialization
- Session lifecycle via API
- Error handling
"""

import pytest
import time

from ..api.models import (
    CompileRulesRequest,
    CreateSessionRequest,
    UploadPhotoRequest,
    SubmitCorrectionRequest,
    SessionStatus,
    CompilationStatus,
    PlayerInfo,
    CardInfo,
    QuestionInfo,
)
from ..api.service import APIService


class TestAPIService:
    """Tests for APIService."""

    @pytest.fixture
    def service(self):
        """Create a fresh API service."""
        return APIService()

    def test_create_innovation_session(self, service):
        """Can create an Innovation session via API."""
        request = CreateSessionRequest(
            game_type="innovation",
            num_automas=1,
            human_player_name="Test Player",
        )

        response = service.create_session(request)

        assert response.session_id is not None
        assert response.status in [SessionStatus.CREATED, SessionStatus.ACTIVE]
        assert response.game_name == "Innovation (Base Game)"
        assert len(response.players) == 2  # Human + 1 bot

    def test_get_session(self, service):
        """Can get session status."""
        # Create session first
        create_request = CreateSessionRequest(game_type="innovation")
        create_response = service.create_session(create_request)

        # Get session
        response = service.get_session(create_response.session_id)

        assert response.session_id == create_response.session_id
        assert response.game_name == "Innovation (Base Game)"

    def test_get_nonexistent_session(self, service):
        """Getting nonexistent session returns error."""
        response = service.get_session("nonexistent-id")

        assert hasattr(response, "error")
        assert response.error_code == "SESSION_NOT_FOUND"

    def test_end_session(self, service):
        """Can end a session."""
        # Create session
        create_request = CreateSessionRequest(game_type="innovation")
        create_response = service.create_session(create_request)
        session_id = create_response.session_id

        # End session
        success = service.end_session(session_id)
        assert success

        # Session should no longer exist
        response = service.get_session(session_id)
        assert hasattr(response, "error")

    def test_list_sessions(self, service):
        """Can list active sessions."""
        # Create a few sessions
        for _ in range(3):
            request = CreateSessionRequest(game_type="innovation")
            service.create_session(request)

        sessions = service.list_sessions()
        assert len(sessions) >= 3

    def test_get_game_state(self, service):
        """Can get full game state."""
        # Create session
        create_request = CreateSessionRequest(game_type="innovation")
        create_response = service.create_session(create_request)

        # Get state
        response = service.get_game_state(create_response.session_id)

        assert response.session_id == create_response.session_id
        assert response.achievements_to_win == 6  # 2 players
        assert len(response.players) == 2

    def test_get_instructions(self, service):
        """Can get pending instructions."""
        # Create session
        create_request = CreateSessionRequest(game_type="innovation")
        create_response = service.create_session(create_request)

        # Get instructions
        response = service.get_instructions(create_response.session_id)

        assert response.session_id == create_response.session_id
        assert hasattr(response, "instructions")


class TestAPIModels:
    """Tests for API model serialization."""

    def test_player_info_creation(self):
        """Can create PlayerInfo."""
        player = PlayerInfo(
            player_id="player1",
            name="Test Player",
            is_human=True,
            is_current_turn=True,
            score=10,
            achievement_count=2,
        )
        assert player.player_id == "player1"
        assert player.is_human
        assert player.score == 10

    def test_card_info_creation(self):
        """Can create CardInfo."""
        card = CardInfo(
            card_id="archery",
            name="Archery",
            age=1,
            color="red",
        )
        assert card.card_id == "archery"
        assert card.age == 1

    def test_question_info_creation(self):
        """Can create QuestionInfo."""
        from ..api.models import CorrectionType

        question = QuestionInfo(
            question_id="q1",
            question_type=CorrectionType.CARD_IDENTITY,
            question_text="What card is this?",
            options=[{"label": "Archery"}, {"label": "Writing"}],
            is_required=True,
        )
        assert question.question_id == "q1"
        assert len(question.options) == 2

    def test_session_status_values(self):
        """SessionStatus enum has expected values."""
        assert SessionStatus.CREATED.value == "created"
        assert SessionStatus.ACTIVE.value == "active"
        assert SessionStatus.YOUR_TURN.value == "your_turn"
        assert SessionStatus.GAME_OVER.value == "game_over"


class TestPhotoProcessing:
    """Tests for photo processing via API."""

    @pytest.fixture
    def service_with_session(self):
        """Create service with active session."""
        service = APIService()
        request = CreateSessionRequest(game_type="innovation")
        response = service.create_session(request)
        return service, response.session_id

    def test_process_empty_photo(self, service_with_session):
        """Processing empty photo returns result."""
        service, session_id = service_with_session

        # Send minimal "photo" (just bytes)
        fake_photo = b"fake image data"
        response = service.process_photo(session_id, fake_photo)

        # Should not crash, even with mock processor
        assert response.session_id == session_id
        assert hasattr(response, "status")

    def test_process_photo_with_metadata(self, service_with_session):
        """Can process photo with metadata."""
        service, session_id = service_with_session

        metadata = UploadPhotoRequest(
            session_id=session_id,
            timestamp=time.time(),
            player_hints={"human": "bottom", "bot_1": "top"},
        )

        response = service.process_photo(session_id, b"fake", metadata)
        assert response.session_id == session_id


class TestCorrections:
    """Tests for correction submission."""

    @pytest.fixture
    def service_with_session(self):
        """Create service with active session."""
        service = APIService()
        request = CreateSessionRequest(game_type="innovation")
        response = service.create_session(request)
        return service, response.session_id

    def test_submit_empty_corrections(self, service_with_session):
        """Can submit empty corrections."""
        service, session_id = service_with_session

        request = SubmitCorrectionRequest(
            session_id=session_id,
            corrections={},
        )

        response = service.submit_corrections(request)
        assert response.session_id == session_id

    def test_submit_corrections_with_values(self, service_with_session):
        """Can submit corrections with values."""
        service, session_id = service_with_session

        request = SubmitCorrectionRequest(
            session_id=session_id,
            corrections={
                "q1": "archery",
                "q2": 3,
            },
        )

        response = service.submit_corrections(request)
        assert response.session_id == session_id


class TestMultipleSessions:
    """Tests for multiple concurrent sessions."""

    def test_sessions_are_independent(self):
        """Multiple sessions don't interfere."""
        service = APIService()

        # Create two sessions
        request1 = CreateSessionRequest(game_type="innovation", num_automas=1)
        request2 = CreateSessionRequest(game_type="innovation", num_automas=2)

        response1 = service.create_session(request1)
        response2 = service.create_session(request2)

        # Should have different IDs
        assert response1.session_id != response2.session_id

        # Should have different player counts
        assert len(response1.players) == 2  # human + 1 bot
        assert len(response2.players) == 3  # human + 2 bots

        # Ending one shouldn't affect the other
        service.end_session(response1.session_id)

        state2 = service.get_session(response2.session_id)
        assert not hasattr(state2, "error")
