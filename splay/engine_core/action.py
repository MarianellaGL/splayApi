"""
Action System - Actions, payloads, and results.

Actions represent:
1. Player actions (draw, meld, dogma, achieve)
2. System actions (setup, end turn, game over)
3. Vision corrections (state update from photo)

All state changes flow through actions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionType(Enum):
    """Types of actions in the system."""
    # Player actions (Innovation)
    DRAW = "draw"
    MELD = "meld"
    DOGMA = "dogma"
    ACHIEVE = "achieve"

    # Generic player actions
    PASS = "pass"
    CHOOSE = "choose"  # Response to a pending choice

    # System actions
    SETUP_GAME = "setup_game"
    START_TURN = "start_turn"
    END_TURN = "end_turn"
    END_GAME = "end_game"

    # Vision-driven actions
    VISION_UPDATE = "vision_update"  # State reconciliation from photo
    USER_CORRECTION = "user_correction"  # Manual state fix
    DECLARE_HAND = "declare_hand"  # Private zone declaration

    # Automa actions (instruction to human)
    AUTOMA_INSTRUCTION = "automa_instruction"


@dataclass
class ActionPayload:
    """
    Payload for an action - contains the action parameters.

    Different action types have different payload shapes.
    This is a generic container; validation happens in the reducer.
    """
    # Common fields
    player_id: str | None = None
    card_id: str | None = None
    target_player_id: str | None = None

    # For choice responses
    choice_index: int | None = None
    choice_values: list[str] | None = None

    # For zone operations
    source_zone: str | None = None
    target_zone: str | None = None
    color: str | None = None

    # For vision updates
    vision_proposal: Any | None = None  # VisionStateProposal
    corrections: dict[str, Any] | None = None

    # For automa instructions
    instruction_text: str | None = None
    physical_actions: list[str] | None = None

    # Generic params
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Action:
    """
    A complete action to be applied to the game state.

    Actions are:
    - Logged for replay
    - Validated before application
    - Applied atomically by the reducer
    """
    action_type: ActionType
    payload: ActionPayload
    timestamp: float | None = None
    action_id: str | None = None

    @classmethod
    def draw(cls, player_id: str, age: int | None = None) -> Action:
        """Factory for draw action."""
        return cls(
            action_type=ActionType.DRAW,
            payload=ActionPayload(player_id=player_id, params={"age": age}),
        )

    @classmethod
    def meld(cls, player_id: str, card_id: str) -> Action:
        """Factory for meld action."""
        return cls(
            action_type=ActionType.MELD,
            payload=ActionPayload(player_id=player_id, card_id=card_id),
        )

    @classmethod
    def dogma(cls, player_id: str, card_id: str) -> Action:
        """Factory for dogma action."""
        return cls(
            action_type=ActionType.DOGMA,
            payload=ActionPayload(player_id=player_id, card_id=card_id),
        )

    @classmethod
    def achieve(cls, player_id: str, achievement_id: str) -> Action:
        """Factory for achieve action."""
        return cls(
            action_type=ActionType.ACHIEVE,
            payload=ActionPayload(player_id=player_id, card_id=achievement_id),
        )

    @classmethod
    def choose(cls, player_id: str, choice_values: list[str]) -> Action:
        """Factory for choice response."""
        return cls(
            action_type=ActionType.CHOOSE,
            payload=ActionPayload(player_id=player_id, choice_values=choice_values),
        )

    @classmethod
    def vision_update(cls, proposal: Any) -> Action:
        """Factory for vision-driven state update."""
        return cls(
            action_type=ActionType.VISION_UPDATE,
            payload=ActionPayload(vision_proposal=proposal),
        )

    @classmethod
    def user_correction(cls, corrections: dict[str, Any]) -> Action:
        """Factory for manual user correction."""
        return cls(
            action_type=ActionType.USER_CORRECTION,
            payload=ActionPayload(corrections=corrections),
        )


@dataclass
class ActionResult:
    """
    Result of applying an action.

    Contains:
    - Whether action succeeded
    - New state (if succeeded)
    - Errors (if failed)
    - Side effects (for UI updates)
    """
    success: bool
    new_state: Any | None = None  # GameState
    error: str | None = None
    error_code: str | None = None

    # For UI/presentation
    state_changes: list[str] = field(default_factory=list)  # Human-readable changes
    automa_instructions: list[str] = field(default_factory=list)  # What human should do

    # For effect resolution
    pending_choice: Any | None = None  # If action triggered a choice
    effects_resolved: list[str] = field(default_factory=list)

    @classmethod
    def failure(cls, error: str, error_code: str | None = None) -> ActionResult:
        """Create a failure result."""
        return cls(success=False, error=error, error_code=error_code)

    @classmethod
    def success_with_state(
        cls,
        state: Any,
        changes: list[str] | None = None,
        instructions: list[str] | None = None,
    ) -> ActionResult:
        """Create a success result with new state."""
        return cls(
            success=True,
            new_state=state,
            state_changes=changes or [],
            automa_instructions=instructions or [],
        )
