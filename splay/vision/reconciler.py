"""
State Reconciler - Reconciles vision proposals with canonical state.

The reconciler is the bridge between vision (non-authoritative)
and the engine (authoritative). It:

1. Validates vision proposals against game rules
2. Detects impossible states
3. Identifies conflicts with previous state
4. Requests user corrections when needed
5. Updates canonical state

Key principle: The ENGINE owns canonical state, not vision.
Vision proposes, engine validates, user confirms, engine commits.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from .proposal import (
    VisionStateProposal,
    DetectedPlayer,
    DetectedCard,
    DetectedZone,
    UncertainZone,
    ConfidenceLevel,
)

if TYPE_CHECKING:
    from ..engine_core.state import GameState, PlayerState
    from ..spec_schema import GameSpec


class ConflictType(Enum):
    """Types of conflicts between vision and canonical state."""
    CARD_MOVED = "card_moved"  # Card appeared/disappeared unexpectedly
    CARD_COUNT_MISMATCH = "card_count_mismatch"  # Different number of cards
    IMPOSSIBLE_STATE = "impossible_state"  # Rules violation
    SPLAY_CHANGED = "splay_changed"  # Splay direction changed
    ACHIEVEMENT_CLAIMED = "achievement_claimed"  # Achievement moved
    UNKNOWN_CARD = "unknown_card"  # Card not in spec


class ConflictSeverity(Enum):
    """Severity of a conflict."""
    INFO = "info"  # Expected change (e.g., after automa turn)
    WARNING = "warning"  # Unexpected but possible
    ERROR = "error"  # Impossible - needs correction


@dataclass
class Conflict:
    """
    A conflict between vision proposal and canonical state.
    """
    conflict_id: str
    conflict_type: ConflictType
    severity: ConflictSeverity
    description: str

    # Where the conflict is
    zone_id: str | None = None
    player_id: str | None = None
    card_id: str | None = None

    # What we expected vs what we saw
    expected_value: Any = None
    detected_value: Any = None

    # For user resolution
    question: str | None = None
    options: list[Any] = field(default_factory=list)

    # Resolution (filled after user input)
    resolved: bool = False
    resolution: Any = None


@dataclass
class ReconciliationResult:
    """
    Result of reconciling vision with canonical state.
    """
    success: bool
    new_state: GameState | None = None

    # Conflicts found
    conflicts: list[Conflict] = field(default_factory=list)

    # Uncertainties that need user input
    uncertainties_remaining: list[UncertainZone] = field(default_factory=list)

    # Changes detected (for UI feedback)
    changes_detected: list[str] = field(default_factory=list)

    # Errors that prevent reconciliation
    errors: list[str] = field(default_factory=list)

    @property
    def needs_user_input(self) -> bool:
        """Check if user input is needed to proceed."""
        return (
            len(self.uncertainties_remaining) > 0
            or any(c.severity == ConflictSeverity.ERROR and not c.resolved for c in self.conflicts)
        )

    def get_questions(self) -> list[dict[str, Any]]:
        """Get questions to ask user for resolution."""
        questions = []

        for unc in self.uncertainties_remaining:
            questions.append({
                "id": unc.zone_id,
                "type": "uncertainty",
                "question": unc.question,
                "alternatives": unc.alternatives,
                "detected_value": unc.detected_value,
            })

        for conflict in self.conflicts:
            if conflict.severity == ConflictSeverity.ERROR and not conflict.resolved:
                questions.append({
                    "id": conflict.conflict_id,
                    "type": "conflict",
                    "question": conflict.question or conflict.description,
                    "options": conflict.options,
                    "expected": conflict.expected_value,
                    "detected": conflict.detected_value,
                })

        return questions


@dataclass
class StateReconciler:
    """
    Reconciles vision proposals with canonical game state.

    The reconciler maintains context about:
    - What changes are expected (automa just moved)
    - What changes are unexpected (user did something)
    - History of reconciliations
    """
    spec: GameSpec

    # Expected changes (set after automa turn)
    expected_changes: list[str] = field(default_factory=list)

    def reconcile(
        self,
        proposal: VisionStateProposal,
        canonical_state: GameState,
    ) -> ReconciliationResult:
        """
        Reconcile a vision proposal with canonical state.

        Steps:
        1. Validate proposal against rules
        2. Compare to canonical state
        3. Identify conflicts
        4. Determine which changes are legal
        5. Return result with questions if needed
        """
        conflicts = []
        changes = []
        errors = []

        # Step 1: Validate proposal against rules
        validation_errors = self._validate_proposal(proposal)
        if validation_errors:
            errors.extend(validation_errors)

        # Step 2: Compare each player's state
        for detected_player in proposal.players:
            player_conflicts, player_changes = self._compare_player_state(
                detected_player,
                canonical_state,
            )
            conflicts.extend(player_conflicts)
            changes.extend(player_changes)

        # Step 3: Compare shared zones
        shared_conflicts, shared_changes = self._compare_shared_zones(
            proposal,
            canonical_state,
        )
        conflicts.extend(shared_conflicts)
        changes.extend(shared_changes)

        # Step 4: Check if changes are legal
        for conflict in conflicts:
            self._assess_conflict_severity(conflict, canonical_state)

        # Step 5: Build new state if no blocking errors
        blocking_errors = [c for c in conflicts if c.severity == ConflictSeverity.ERROR]
        if not blocking_errors and not errors:
            new_state = self._build_new_state(proposal, canonical_state)
        else:
            new_state = None

        return ReconciliationResult(
            success=new_state is not None,
            new_state=new_state,
            conflicts=conflicts,
            uncertainties_remaining=proposal.uncertain_zones.copy(),
            changes_detected=changes,
            errors=errors,
        )

    def apply_corrections(
        self,
        result: ReconciliationResult,
        corrections: dict[str, Any],
    ) -> ReconciliationResult:
        """
        Apply user corrections and re-reconcile.

        corrections is a dict mapping conflict_id/zone_id to resolution value.
        """
        # Apply corrections to conflicts
        for conflict in result.conflicts:
            if conflict.conflict_id in corrections:
                conflict.resolved = True
                conflict.resolution = corrections[conflict.conflict_id]

        # Clear resolved uncertainties
        new_uncertainties = []
        for unc in result.uncertainties_remaining:
            if unc.zone_id not in corrections:
                new_uncertainties.append(unc)

        result.uncertainties_remaining = new_uncertainties

        # If all resolved, build state
        if not result.needs_user_input:
            # STUB: Build state from corrections
            pass

        return result

    def set_expected_changes(self, changes: list[str]):
        """
        Set expected changes for next reconciliation.

        Called after automa turn to indicate what should have changed.
        """
        self.expected_changes = changes

    def clear_expected_changes(self):
        """Clear expected changes after successful reconciliation."""
        self.expected_changes = []

    def _validate_proposal(self, proposal: VisionStateProposal) -> list[str]:
        """Validate proposal against game rules."""
        errors = []

        # Check for impossible states
        total_cards_seen = 0
        for player in proposal.players:
            for color, pile in player.board_piles.items():
                total_cards_seen += len(pile.cards)

        # STUB: Check against spec constraints
        # e.g., total cards shouldn't exceed deck size

        return errors

    def _compare_player_state(
        self,
        detected: DetectedPlayer,
        canonical: GameState,
    ) -> tuple[list[Conflict], list[str]]:
        """Compare detected player state with canonical."""
        conflicts = []
        changes = []

        canonical_player = canonical.get_player(detected.player_id)
        if not canonical_player:
            # New player or misidentified
            conflicts.append(
                Conflict(
                    conflict_id=f"player_{detected.player_id}",
                    conflict_type=ConflictType.IMPOSSIBLE_STATE,
                    severity=ConflictSeverity.ERROR,
                    description=f"Unknown player: {detected.player_id}",
                    player_id=detected.player_id,
                    question=f"Player {detected.player_id} not found. Is this a valid player?",
                )
            )
            return conflicts, changes

        # Compare board piles
        for color, detected_pile in detected.board_piles.items():
            canonical_stack = canonical_player.get_board_stack(color)

            # Compare top card
            if detected_pile.cards and canonical_stack.top_card:
                detected_top = detected_pile.cards[0]
                if detected_top.matched_card_id != canonical_stack.top_card.card_id:
                    changes.append(f"{color} pile top card changed")
                    conflicts.append(
                        Conflict(
                            conflict_id=f"{detected.player_id}_{color}_top",
                            conflict_type=ConflictType.CARD_MOVED,
                            severity=ConflictSeverity.WARNING,  # Might be expected
                            description=f"Top card of {color} pile changed",
                            zone_id=f"{detected.player_id}_board_{color}",
                            player_id=detected.player_id,
                            expected_value=canonical_stack.top_card.card_id,
                            detected_value=detected_top.matched_card_id,
                        )
                    )

            # Compare splay
            if detected_pile.splay_direction.value != canonical_stack.splay_direction.value:
                if detected_pile.splay_direction.value != "unknown":
                    changes.append(f"{color} pile splay changed")

        return conflicts, changes

    def _compare_shared_zones(
        self,
        proposal: VisionStateProposal,
        canonical: GameState,
    ) -> tuple[list[Conflict], list[str]]:
        """Compare detected shared zones with canonical."""
        conflicts = []
        changes = []

        # Compare achievements
        detected_achievement_ids = {
            c.matched_card_id for c in proposal.achievements_available
            if c.matched_card_id
        }
        canonical_achievement_ids = {
            c.card_id for c in canonical.achievements.cards
        }

        missing = canonical_achievement_ids - detected_achievement_ids
        if missing:
            changes.append(f"Achievements claimed: {missing}")

        # Compare deck sizes
        for age, detected_size in proposal.deck_sizes.items():
            deck_key = f"age_{age}"
            canonical_deck = canonical.supply_decks.get(deck_key)
            if canonical_deck:
                if abs(detected_size - canonical_deck.count) > 2:  # Allow some variance
                    conflicts.append(
                        Conflict(
                            conflict_id=f"deck_{age}",
                            conflict_type=ConflictType.CARD_COUNT_MISMATCH,
                            severity=ConflictSeverity.WARNING,
                            description=f"Age {age} deck size mismatch",
                            zone_id=deck_key,
                            expected_value=canonical_deck.count,
                            detected_value=detected_size,
                        )
                    )

        return conflicts, changes

    def _assess_conflict_severity(
        self,
        conflict: Conflict,
        canonical: GameState,
    ):
        """
        Determine severity of a conflict.

        Considers expected changes and game rules.
        """
        # If change was expected, lower severity
        if conflict.description in self.expected_changes:
            if conflict.severity == ConflictSeverity.ERROR:
                conflict.severity = ConflictSeverity.INFO
            return

        # STUB: More sophisticated rule checking
        # e.g., is this card movement legal?

    def _build_new_state(
        self,
        proposal: VisionStateProposal,
        canonical: GameState,
    ) -> GameState:
        """
        Build new canonical state from proposal.

        Only called when reconciliation succeeds.
        """
        # STUB: Implement state building
        # For now, return canonical unchanged
        return canonical
