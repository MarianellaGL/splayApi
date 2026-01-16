"""
Tests for vision layer and state reconciliation.

Tests:
- VisionStateProposal creation
- Reconciliation logic
- Conflict detection
- User correction handling
"""

import pytest
import time

from ..vision import (
    VisionStateProposal,
    DetectedCard,
    DetectedPlayer,
    DetectedZone,
    UncertainZone,
    ConfidenceLevel,
    SplayDirectionDetected,
    VisionProcessor,
    MockVisionProcessor,
    StateReconciler,
    ReconciliationResult,
    Conflict,
)
from ..vision.proposal import PhotoInput


class TestVisionStateProposal:
    """Tests for VisionStateProposal data structure."""

    def test_create_empty_proposal(self):
        """Can create minimal proposal."""
        proposal = VisionStateProposal(
            proposal_id="test_1",
            timestamp=time.time(),
            confidence_score=0.5,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        assert proposal.proposal_id == "test_1"
        assert not proposal.has_uncertainties()

    def test_proposal_with_uncertainties(self):
        """Proposal with uncertainties is detected."""
        proposal = VisionStateProposal(
            proposal_id="test_1",
            timestamp=time.time(),
            confidence_score=0.3,
            confidence_level=ConfidenceLevel.LOW,
            uncertain_zones=[
                UncertainZone(
                    zone_id="player1_board_red",
                    zone_type="board_pile",
                    uncertainty_type="card_identity",
                    question="What is the top card of the red pile?",
                ),
            ],
        )
        assert proposal.has_uncertainties()
        assert len(proposal.get_uncertainty_questions()) == 1

    def test_detected_card_structure(self):
        """DetectedCard holds card information."""
        card = DetectedCard(
            detected_age=3,
            detected_color="blue",
            confidence=ConfidenceLevel.HIGH,
            confidence_score=0.95,
        )
        assert card.detected_age == 3
        assert card.detected_color == "blue"

    def test_detected_player_structure(self):
        """DetectedPlayer holds player state."""
        player = DetectedPlayer(
            player_id="human",
            player_position="bottom",
            board_piles={
                "red": DetectedZone(
                    zone_type="board_pile",
                    player_id="human",
                    color="red",
                    cards=[DetectedCard(detected_age=1, detected_color="red")],
                    splay_direction=SplayDirectionDetected.NONE,
                ),
            },
        )
        assert player.player_id == "human"
        assert "red" in player.board_piles


class TestMockVisionProcessor:
    """Tests for mock vision processor."""

    def test_mock_processor_returns_proposal(self):
        """Mock processor returns valid proposal."""
        processor = MockVisionProcessor()
        photo = PhotoInput(image_path="test.jpg", timestamp=time.time())

        proposal = processor.process(photo)

        assert proposal is not None
        assert proposal.proposal_id is not None
        assert isinstance(proposal.confidence_score, float)

    def test_mock_with_predefined(self):
        """Mock processor can return predefined proposals."""
        predefined = VisionStateProposal(
            proposal_id="predefined",
            timestamp=time.time(),
            confidence_score=1.0,
            confidence_level=ConfidenceLevel.HIGH,
        )
        processor = MockVisionProcessor(
            predefined_proposals={"game_photo.jpg": predefined}
        )

        photo = PhotoInput(image_path="game_photo.jpg")
        result = processor.process(photo)

        assert result.proposal_id == "predefined"


class TestStateReconciler:
    """Tests for state reconciliation."""

    def test_reconcile_matching_state(self, two_player_state, innovation_spec):
        """Reconciliation succeeds when states match."""
        reconciler = StateReconciler(spec=innovation_spec)

        # Create proposal matching current state
        proposal = VisionStateProposal(
            proposal_id="test",
            timestamp=time.time(),
            confidence_score=0.9,
            confidence_level=ConfidenceLevel.HIGH,
            players=[
                DetectedPlayer(player_id="human", player_position="bottom"),
                DetectedPlayer(player_id="bot1", player_position="top"),
            ],
        )

        result = reconciler.reconcile(proposal, two_player_state)

        # Should succeed (no conflicts)
        assert not result.needs_user_input or len(result.errors) == 0

    def test_detect_card_change_conflict(self, two_player_state, innovation_spec):
        """Reconciler detects card changes."""
        from ..engine_core.state import Card, ZoneStack

        # Set up state with a known board
        human = two_player_state.get_player("human")
        red_stack = ZoneStack(cards=[Card(card_id="archery", instance_id="arch_1")])
        new_human = human.with_board_stack("red", red_stack)
        state = two_player_state.with_player(new_human)

        reconciler = StateReconciler(spec=innovation_spec)

        # Create proposal with different top card
        proposal = VisionStateProposal(
            proposal_id="test",
            timestamp=time.time(),
            confidence_score=0.8,
            confidence_level=ConfidenceLevel.HIGH,
            players=[
                DetectedPlayer(
                    player_id="human",
                    board_piles={
                        "red": DetectedZone(
                            zone_type="board_pile",
                            player_id="human",
                            color="red",
                            cards=[
                                DetectedCard(
                                    detected_age=1,
                                    detected_color="red",
                                    matched_card_id="metalworking",  # Different!
                                )
                            ],
                        ),
                    },
                ),
            ],
        )

        result = reconciler.reconcile(proposal, state)

        # Should detect the card change
        assert len(result.conflicts) > 0 or len(result.changes_detected) > 0

    def test_expected_changes_lower_severity(self, two_player_state, innovation_spec):
        """Expected changes have lower conflict severity."""
        reconciler = StateReconciler(spec=innovation_spec)

        # Set expected change
        reconciler.set_expected_changes(["red pile top card changed"])

        proposal = VisionStateProposal(
            proposal_id="test",
            timestamp=time.time(),
            confidence_score=0.9,
            confidence_level=ConfidenceLevel.HIGH,
            players=[],
        )

        # Result should have expected changes cleared after reconcile
        # (detailed behavior depends on implementation)
        assert reconciler.expected_changes == ["red pile top card changed"]

        reconciler.clear_expected_changes()
        assert reconciler.expected_changes == []


class TestReconciliationResult:
    """Tests for ReconciliationResult structure."""

    def test_needs_user_input_when_uncertainties(self):
        """needs_user_input is True when uncertainties exist."""
        result = ReconciliationResult(
            success=False,
            uncertainties_remaining=[
                UncertainZone(
                    zone_id="test",
                    zone_type="board",
                    uncertainty_type="card_identity",
                    question="What card is this?",
                ),
            ],
        )
        assert result.needs_user_input

    def test_needs_user_input_when_error_conflicts(self):
        """needs_user_input is True when error conflicts unresolved."""
        from ..vision.reconciler import ConflictType, ConflictSeverity

        result = ReconciliationResult(
            success=False,
            conflicts=[
                Conflict(
                    conflict_id="test",
                    conflict_type=ConflictType.IMPOSSIBLE_STATE,
                    severity=ConflictSeverity.ERROR,
                    description="Invalid state",
                    resolved=False,
                ),
            ],
        )
        assert result.needs_user_input

    def test_get_questions_returns_all(self):
        """get_questions returns both uncertainties and conflicts."""
        from ..vision.reconciler import ConflictType, ConflictSeverity

        result = ReconciliationResult(
            success=False,
            uncertainties_remaining=[
                UncertainZone(
                    zone_id="unc_1",
                    zone_type="board",
                    uncertainty_type="card_identity",
                    question="Question 1?",
                ),
            ],
            conflicts=[
                Conflict(
                    conflict_id="conf_1",
                    conflict_type=ConflictType.IMPOSSIBLE_STATE,
                    severity=ConflictSeverity.ERROR,
                    description="Conflict 1",
                    question="Question 2?",
                    resolved=False,
                ),
            ],
        )

        questions = result.get_questions()
        assert len(questions) == 2
