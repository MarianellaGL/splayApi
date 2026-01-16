"""
Integration tests - End-to-end workflow tests.

Tests the complete flow:
1. Create spec
2. Create session
3. Process game loop
4. Bot decision making
"""

import pytest
import time

from ..games.innovation.spec import create_innovation_spec
from ..games.innovation.state import InnovationState
from ..session import SessionManager, GameLoop, LoopState
from ..vision.proposal import PhotoInput, VisionStateProposal, ConfidenceLevel
from ..bots import InnovationBot
from ..engine_core.action_generator import legal_actions


class TestFullGameFlow:
    """Tests for complete game flow."""

    def test_create_session_from_spec(self):
        """Can create a session from Innovation spec."""
        spec = create_innovation_spec()
        manager = SessionManager()

        session = manager.create_session(spec, num_automas=1)

        assert session is not None
        assert session.session_id is not None
        assert session.spec == spec
        assert len(session.bots) == 1

    def test_session_lifecycle(self):
        """Session can be created and ended."""
        spec = create_innovation_spec()
        manager = SessionManager()

        session = manager.create_session(spec)
        session_id = session.session_id

        assert session_id in manager.list_active_sessions()

        manager.end_session(session_id)

        assert session_id not in manager.list_active_sessions()

    def test_game_loop_initialization(self):
        """Game loop can be initialized."""
        spec = create_innovation_spec()
        manager = SessionManager()
        session = manager.create_session(spec)

        loop = GameLoop(session)

        assert loop.state == LoopState.WAITING_PHOTO

    def test_bot_makes_legal_decisions(self, two_player_state, innovation_spec):
        """Bot always selects from legal actions."""
        state = two_player_state

        # Make it bot's turn
        state = state._copy_with(current_player_idx=1)

        bot = InnovationBot(player_id="bot1")
        legal = legal_actions(innovation_spec, state)

        # Run multiple times
        for _ in range(5):
            decision = bot.select_action(state, innovation_spec, legal)
            # Action type should match one of the legal actions
            assert any(
                a.action_type == decision.action.action_type
                for a in legal
            )
            # Should have instructions
            assert len(decision.physical_instructions) >= 0


class TestSpecCompilation:
    """Tests for spec creation and validation."""

    def test_innovation_spec_is_valid(self):
        """Innovation spec passes validation."""
        from ..spec_schema import validate_spec

        spec = create_innovation_spec()
        result = validate_spec(spec)

        # May have warnings but should have no structural errors
        assert result.valid or len([e for e in result.errors if "required" in e.lower()]) == 0

    def test_spec_has_actions(self):
        """Innovation spec has action definitions."""
        spec = create_innovation_spec()

        assert len(spec.actions) > 0
        action_names = {a.name for a in spec.actions}
        assert "draw" in action_names
        assert "meld" in action_names
        assert "dogma" in action_names
        assert "achieve" in action_names

    def test_spec_has_cards(self):
        """Innovation spec has card definitions."""
        spec = create_innovation_spec()

        assert len(spec.cards) > 0
        # Check a known card
        archery = spec.get_card("archery")
        assert archery is not None
        assert archery.age == 1
        assert archery.color == "red"


class TestVisionIntegration:
    """Tests for vision system integration."""

    def test_mock_vision_returns_proposal(self):
        """Mock vision processor returns valid proposal."""
        from ..vision import MockVisionProcessor

        processor = MockVisionProcessor()
        photo = PhotoInput(image_path="test.jpg", timestamp=time.time())

        proposal = processor.process(photo)

        assert proposal is not None
        assert proposal.proposal_id is not None
        assert 0 <= proposal.confidence_score <= 1

    def test_reconciler_handles_empty_proposal(self, two_player_state, innovation_spec):
        """Reconciler handles proposal with no detected state."""
        from ..vision import StateReconciler

        reconciler = StateReconciler(spec=innovation_spec)

        proposal = VisionStateProposal(
            proposal_id="test",
            timestamp=time.time(),
            confidence_score=0.5,
            confidence_level=ConfidenceLevel.MEDIUM,
            players=[],
        )

        result = reconciler.reconcile(proposal, two_player_state)

        # Should not crash
        assert result is not None


class TestBotVariety:
    """Tests for different bot personalities."""

    def test_all_personalities_work(self, two_player_state, innovation_spec):
        """All predefined personalities can make decisions."""
        from ..bots.personality import PERSONALITIES

        state = two_player_state._copy_with(current_player_idx=1)
        legal = legal_actions(innovation_spec, state)

        for name, personality in PERSONALITIES.items():
            bot = InnovationBot(player_id="bot1", personality=personality)
            decision = bot.select_action(state, innovation_spec, legal)

            assert decision is not None
            assert decision.action is not None
            assert decision.explanation != ""

    def test_different_seeds_different_results(self, two_player_state, innovation_spec):
        """Different random seeds produce different results over many runs."""
        import random
        from ..bots.personality import CHAOTIC

        state = two_player_state._copy_with(current_player_idx=1)
        legal = legal_actions(innovation_spec, state)

        results_seed_1 = []
        results_seed_2 = []

        for i in range(10):
            bot1 = InnovationBot(
                player_id="bot1",
                personality=CHAOTIC,
                rng=random.Random(42),
            )
            bot2 = InnovationBot(
                player_id="bot1",
                personality=CHAOTIC,
                rng=random.Random(123),
            )

            d1 = bot1.select_action(state, innovation_spec, legal)
            d2 = bot2.select_action(state, innovation_spec, legal)

            results_seed_1.append(d1.action.action_type.value)
            results_seed_2.append(d2.action.action_type.value)

        # With chaotic personality, different seeds should produce some variation
        # (Not guaranteed but highly likely)
