"""
Structured Corrections - Typed models for user state corrections.

These models replace generic dict-based corrections with explicit,
validated types. This enables:
- Type checking at parse time
- Clear documentation of correction types
- Proper validation in reducer/reconciler

Correction Types:
- SetCard: Set a card in a specific zone
- SetSplay: Set splay direction for a color pile
- ConfirmZone: Confirm zone contents are correct
- AnswerQuestion: Answer a clarification question
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Union


class CorrectionType(Enum):
    """Types of corrections a user can make."""
    SET_CARD = "set_card"
    SET_SPLAY = "set_splay"
    CONFIRM_ZONE = "confirm_zone"
    ANSWER_QUESTION = "answer_question"
    SET_CARD_COUNT = "set_card_count"
    SET_DECK_SIZE = "set_deck_size"


@dataclass
class SetCard:
    """
    Set a specific card in a zone.

    Used when vision detected a card but user corrects the identity.

    Examples:
        SetCard(zone_id="human_board_blue", card_id="writing", position="top")
        SetCard(zone_id="human_hand", card_id="archery")
    """
    zone_id: str
    card_id: str
    position: str = "top"  # "top", "bottom", or index
    player_id: str | None = None  # Optional if zone_id contains player

    @property
    def correction_type(self) -> CorrectionType:
        return CorrectionType.SET_CARD

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.correction_type.value,
            "zone_id": self.zone_id,
            "card_id": self.card_id,
            "position": self.position,
            "player_id": self.player_id,
        }


@dataclass
class SetSplay:
    """
    Set the splay direction for a player's color pile.

    Examples:
        SetSplay(player_id="human", color="blue", direction="right")
        SetSplay(player_id="bot_1", color="red", direction="none")
    """
    player_id: str
    color: str
    direction: str  # "none", "left", "right", "up"

    @property
    def correction_type(self) -> CorrectionType:
        return CorrectionType.SET_SPLAY

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.correction_type.value,
            "player_id": self.player_id,
            "color": self.color,
            "direction": self.direction,
        }


@dataclass
class ConfirmZone:
    """
    Confirm that a zone's detected contents are correct.

    Used to acknowledge vision was correct without changes.

    Examples:
        ConfirmZone(zone_id="human_board_blue")
        ConfirmZone(zone_id="achievements_supply")
    """
    zone_id: str
    confirmed: bool = True
    player_id: str | None = None

    @property
    def correction_type(self) -> CorrectionType:
        return CorrectionType.CONFIRM_ZONE

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.correction_type.value,
            "zone_id": self.zone_id,
            "confirmed": self.confirmed,
            "player_id": self.player_id,
        }


@dataclass
class AnswerQuestion:
    """
    Answer a clarification question from vision/reconciler.

    Questions have IDs and predefined options.

    Examples:
        AnswerQuestion(question_id="q1", option_id="archery")
        AnswerQuestion(question_id="player_count", option_id="2")
    """
    question_id: str
    option_id: str  # The selected option

    @property
    def correction_type(self) -> CorrectionType:
        return CorrectionType.ANSWER_QUESTION

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.correction_type.value,
            "question_id": self.question_id,
            "option_id": self.option_id,
        }


@dataclass
class SetCardCount:
    """
    Set the card count for a zone (when count differs from detected).

    Examples:
        SetCardCount(zone_id="human_score_pile", count=5)
        SetCardCount(zone_id="bot_1_hand", count=3)
    """
    zone_id: str
    count: int
    player_id: str | None = None

    @property
    def correction_type(self) -> CorrectionType:
        return CorrectionType.SET_CARD_COUNT

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.correction_type.value,
            "zone_id": self.zone_id,
            "count": self.count,
            "player_id": self.player_id,
        }


@dataclass
class SetDeckSize:
    """
    Set the size of an age deck.

    Examples:
        SetDeckSize(age=1, count=8)
        SetDeckSize(age=3, count=10)
    """
    age: int
    count: int

    @property
    def correction_type(self) -> CorrectionType:
        return CorrectionType.SET_DECK_SIZE

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.correction_type.value,
            "age": self.age,
            "count": self.count,
        }


# Union type for all corrections
Correction = Union[SetCard, SetSplay, ConfirmZone, AnswerQuestion, SetCardCount, SetDeckSize]


def parse_correction(data: dict[str, Any]) -> Correction:
    """
    Parse a correction from a dictionary.

    Args:
        data: Dictionary with "type" key and correction-specific fields

    Returns:
        Typed Correction object

    Raises:
        ValueError: If type is unknown or required fields are missing
    """
    correction_type = data.get("type")
    if not correction_type:
        raise ValueError("Correction missing 'type' field")

    try:
        ctype = CorrectionType(correction_type)
    except ValueError:
        raise ValueError(f"Unknown correction type: {correction_type}")

    if ctype == CorrectionType.SET_CARD:
        return SetCard(
            zone_id=data["zone_id"],
            card_id=data["card_id"],
            position=data.get("position", "top"),
            player_id=data.get("player_id"),
        )
    elif ctype == CorrectionType.SET_SPLAY:
        return SetSplay(
            player_id=data["player_id"],
            color=data["color"],
            direction=data["direction"],
        )
    elif ctype == CorrectionType.CONFIRM_ZONE:
        return ConfirmZone(
            zone_id=data["zone_id"],
            confirmed=data.get("confirmed", True),
            player_id=data.get("player_id"),
        )
    elif ctype == CorrectionType.ANSWER_QUESTION:
        return AnswerQuestion(
            question_id=data["question_id"],
            option_id=data["option_id"],
        )
    elif ctype == CorrectionType.SET_CARD_COUNT:
        return SetCardCount(
            zone_id=data["zone_id"],
            count=data["count"],
            player_id=data.get("player_id"),
        )
    elif ctype == CorrectionType.SET_DECK_SIZE:
        return SetDeckSize(
            age=data["age"],
            count=data["count"],
        )
    else:
        raise ValueError(f"Unhandled correction type: {ctype}")


def parse_corrections(data: list[dict[str, Any]]) -> list[Correction]:
    """Parse a list of corrections from dictionaries."""
    return [parse_correction(d) for d in data]


@dataclass
class CorrectionBatch:
    """
    A batch of corrections to apply together.

    Corrections are applied in order. If any correction fails,
    the entire batch is rejected.
    """
    corrections: list[Correction]
    skip_remaining_questions: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CorrectionBatch:
        """Create from API request format."""
        corrections_data = data.get("corrections", [])
        corrections = parse_corrections(corrections_data)
        return cls(
            corrections=corrections,
            skip_remaining_questions=data.get("skip_remaining", False),
        )
