"""
Vision State Proposal - Data structures for vision output.

The VisionStateProposal is what the vision system produces from a photo.
It contains:
- Detected partial game state
- Confidence scores
- Uncertain zones that need user confirmation

For Innovation MVP, vision detects:
- Top card of each pile (age, color, splay direction)
- Achievements in play
- Approximate deck sizes
- Optionally: human hand (via private scan)

Vision does NOT need to detect:
- Full card text
- History of actions
- Hidden opponent hands
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConfidenceLevel(Enum):
    """Confidence levels for detected elements."""
    HIGH = "high"  # >90% confident
    MEDIUM = "medium"  # 60-90% confident
    LOW = "low"  # 30-60% confident
    UNCERTAIN = "uncertain"  # <30% confident


class SplayDirectionDetected(Enum):
    """Detected splay directions."""
    NONE = "none"
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    UNKNOWN = "unknown"


@dataclass
class DetectedCard:
    """
    A card detected from the photo.

    Contains what we can see about the card.
    For Innovation, we primarily need age and color.
    """
    # What we detected
    detected_age: int | None = None
    detected_color: str | None = None
    detected_name: str | None = None  # If OCR worked

    # Confidence
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    confidence_score: float = 0.5

    # Position in image (for debugging/UI)
    bounding_box: tuple[int, int, int, int] | None = None  # x, y, w, h

    # Matched card ID (after reconciliation)
    matched_card_id: str | None = None

    # Raw detection data
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectedZone:
    """
    A detected zone (pile, hand, etc.) from the photo.
    """
    zone_type: str  # "board_pile", "hand", "score_pile", "achievement", "deck"
    player_id: str | None = None  # None for shared zones
    color: str | None = None  # For board piles

    # Cards in this zone (top to bottom if relevant)
    cards: list[DetectedCard] = field(default_factory=list)

    # For board piles: splay direction
    splay_direction: SplayDirectionDetected = SplayDirectionDetected.UNKNOWN

    # How many cards (may differ from len(cards) if we can't see all)
    card_count: int | None = None
    card_count_approximate: bool = True

    # Confidence
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


@dataclass
class DetectedPlayer:
    """
    Detected state for a single player.
    """
    player_id: str
    player_position: str | None = None  # "top", "bottom", "left", "right"

    # Board piles by color
    board_piles: dict[str, DetectedZone] = field(default_factory=dict)

    # Score pile (may only see count)
    score_pile: DetectedZone | None = None
    score_pile_count: int | None = None

    # Achievements
    achievements: list[DetectedCard] = field(default_factory=list)

    # Hand (only if scanned/declared)
    hand: DetectedZone | None = None
    hand_count: int | None = None
    hand_declared: bool = False  # True if user declared, not detected


@dataclass
class UncertainZone:
    """
    A zone where vision is uncertain and needs user confirmation.
    """
    zone_id: str
    zone_type: str
    uncertainty_type: str  # "card_identity", "card_count", "splay_direction"
    question: str  # Human-readable question for UI

    # Optional fields (must come after required fields)
    player_id: str | None = None
    detected_value: Any = None
    alternatives: list[Any] = field(default_factory=list)


@dataclass
class VisionStateProposal:
    """
    Complete state proposal from vision.

    This is the OUTPUT of the vision system.
    The engine will:
    1. Validate this against rules
    2. Reject impossible states
    3. Request user correction for uncertainties
    4. Update canonical state
    """
    # Unique ID for this proposal
    proposal_id: str

    # Timestamp when photo was taken
    timestamp: float

    # Overall confidence
    confidence_score: float  # 0-1
    confidence_level: ConfidenceLevel

    # Detected player states
    players: list[DetectedPlayer] = field(default_factory=list)

    # Shared zones
    achievements_available: list[DetectedCard] = field(default_factory=list)
    deck_sizes: dict[str, int] = field(default_factory=dict)  # age -> count

    # What we're uncertain about
    uncertain_zones: list[UncertainZone] = field(default_factory=list)

    # Validation results (filled by reconciler)
    validation_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)

    # Photo metadata
    photo_path: str | None = None
    photo_hash: str | None = None

    def has_uncertainties(self) -> bool:
        """Check if there are uncertainties needing user input."""
        return len(self.uncertain_zones) > 0

    def get_uncertainty_questions(self) -> list[str]:
        """Get list of questions to ask user."""
        return [u.question for u in self.uncertain_zones]

    def apply_corrections(self, corrections: dict[str, Any]) -> VisionStateProposal:
        """
        Apply user corrections to this proposal.

        Returns a new proposal with corrections applied.
        """
        # STUB: Implement correction application
        # This would update detected values and clear uncertainties
        return self


@dataclass
class PhotoInput:
    """
    Input photo for vision processing.
    """
    image_data: bytes | None = None
    image_path: str | None = None
    timestamp: float = 0.0

    # Hints from user
    player_positions: dict[str, str] | None = None  # player_id -> position
    known_hands: dict[str, list[str]] | None = None  # player_id -> card_ids (if declared)

    # Previous state (for change detection)
    previous_proposal: VisionStateProposal | None = None
