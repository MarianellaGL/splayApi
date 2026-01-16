"""
Vision Processor - Processes photos into state proposals.

This module handles:
1. Image preprocessing
2. Card detection
3. State extraction
4. Confidence scoring

STUB MARKER: The actual ML/CV implementation is deferred.
The interface is complete; implementations can plug in.

For MVP, we support:
- Manual state input (bypass vision)
- Mock processor for testing
- Future: Real CV processor
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import uuid
import time

from .proposal import (
    VisionStateProposal,
    DetectedCard,
    DetectedZone,
    DetectedPlayer,
    UncertainZone,
    ConfidenceLevel,
    SplayDirectionDetected,
    PhotoInput,
)


class VisionProcessor(ABC):
    """
    Abstract base class for vision processors.

    Implementations:
    - MockVisionProcessor: For testing
    - ManualInputProcessor: User types in state
    - CVVisionProcessor: Future ML-based processor
    """

    @abstractmethod
    def process(self, photo: PhotoInput) -> VisionStateProposal:
        """
        Process a photo and return a state proposal.

        This is the main entry point for vision processing.
        """
        pass

    @abstractmethod
    def supports_format(self, format: str) -> bool:
        """Check if processor supports a given image format."""
        pass


class MockVisionProcessor(VisionProcessor):
    """
    Mock vision processor for testing.

    Returns predefined proposals or generates random ones.
    """

    def __init__(self, predefined_proposals: dict[str, VisionStateProposal] | None = None):
        self.predefined_proposals = predefined_proposals or {}

    def process(self, photo: PhotoInput) -> VisionStateProposal:
        """Return predefined proposal or generate mock."""
        if photo.image_path and photo.image_path in self.predefined_proposals:
            return self.predefined_proposals[photo.image_path]

        # Generate mock proposal
        return self._generate_mock_proposal(photo)

    def supports_format(self, format: str) -> bool:
        return True  # Mock supports everything

    def _generate_mock_proposal(self, photo: PhotoInput) -> VisionStateProposal:
        """Generate a mock proposal for testing."""
        return VisionStateProposal(
            proposal_id=str(uuid.uuid4()),
            timestamp=photo.timestamp or time.time(),
            confidence_score=0.8,
            confidence_level=ConfidenceLevel.HIGH,
            players=[],
            achievements_available=[],
            deck_sizes={},
            uncertain_zones=[],
        )


class ManualInputProcessor(VisionProcessor):
    """
    Manual input processor - user provides state directly.

    Used when:
    - Vision is not available
    - Testing specific scenarios
    - User prefers typing over photos
    """

    def process(self, photo: PhotoInput) -> VisionStateProposal:
        """
        Process 'photo' which is actually manual input data.

        The photo.image_data should contain serialized state.
        """
        # STUB: Parse manual input into proposal
        return VisionStateProposal(
            proposal_id=str(uuid.uuid4()),
            timestamp=time.time(),
            confidence_score=1.0,  # Manual input is authoritative
            confidence_level=ConfidenceLevel.HIGH,
            players=[],
            uncertain_zones=[],
        )

    def supports_format(self, format: str) -> bool:
        return format in {"json", "yaml", "manual"}


@dataclass
class PlayerHints:
    """
    Typed hints about player positions and known state.

    Used to help vision processing when positions are known.
    """
    # Player positions: player_id -> position (top, bottom, left, right)
    player_positions: dict[str, str] = field(default_factory=dict)

    # Known hands (if declared by user)
    known_hands: dict[str, list[str]] = field(default_factory=dict)

    # Known top cards (if user confirms)
    known_top_cards: dict[str, str] = field(default_factory=dict)  # "player_color" -> card_id

    # Known splay directions
    known_splays: dict[str, str] = field(default_factory=dict)  # "player_color" -> direction

    @classmethod
    def from_dict(cls, data: dict | None) -> PlayerHints:
        """Create from API request data."""
        if not data:
            return cls()
        return cls(
            player_positions=data.get("player_positions", {}),
            known_hands=data.get("known_hands", {}),
            known_top_cards=data.get("known_top_cards", {}),
            known_splays=data.get("known_splays", {}),
        )


@dataclass
class InnovationVisionConfig:
    """
    Configuration for Innovation-specific vision processing.
    """
    # Card detection settings
    detect_age: bool = True
    detect_color: bool = True
    detect_name: bool = False  # OCR is harder
    detect_splay: bool = True

    # What to detect
    detect_board_piles: bool = True
    detect_achievements: bool = True
    detect_deck_sizes: bool = True
    detect_hands: bool = False  # Usually private

    # Player positions (if known ahead of time)
    player_positions: dict[str, str] = field(default_factory=dict)

    # Reference images for cards (for matching)
    card_reference_path: str | None = None

    # Stub mode: use deterministic fake detection
    stub_mode: bool = True

    # Default cards for stub mode (per color)
    stub_cards: dict[str, list[str]] = field(default_factory=lambda: {
        "red": ["archery", "metalworking"],
        "yellow": ["agriculture", "domestication"],
        "green": ["the_wheel", "clothing"],
        "blue": ["writing", "pottery"],
        "purple": ["code_of_laws", "mysticism"],
    })


class InnovationVisionProcessor(VisionProcessor):
    """
    Vision processor specialized for Innovation.

    For MVP, uses stub detection that returns deterministic results
    based on player hints. Real CV implementation deferred.

    Detects:
    - Top card of each pile (age, color)
    - Splay direction
    - Achievements in play
    - Deck sizes (approximate)
    """

    def __init__(self, config: InnovationVisionConfig | None = None):
        self.config = config or InnovationVisionConfig()
        self._model = None  # Future: ML model

    def process(self, photo: PhotoInput) -> VisionStateProposal:
        """
        Process an Innovation game photo.

        Uses stub detection for MVP - returns deterministic results
        based on player hints provided.
        """
        proposal_id = str(uuid.uuid4())
        timestamp = photo.timestamp or time.time()

        # Parse player hints
        hints = PlayerHints.from_dict(photo.player_positions)

        if self.config.stub_mode:
            return self._stub_process(proposal_id, timestamp, photo, hints)

        # Real CV processing (not implemented)
        players = self._detect_players(photo, hints)
        achievements = self._detect_achievements(photo)
        deck_sizes = self._detect_deck_sizes(photo)
        uncertainties = self._identify_uncertainties(players, achievements, hints)

        confidence = self._calculate_confidence(players, uncertainties)

        return VisionStateProposal(
            proposal_id=proposal_id,
            timestamp=timestamp,
            confidence_score=confidence,
            confidence_level=self._score_to_level(confidence),
            players=players,
            achievements_available=achievements,
            deck_sizes=deck_sizes,
            uncertain_zones=uncertainties,
            photo_path=photo.image_path,
        )

    def _stub_process(
        self,
        proposal_id: str,
        timestamp: float,
        photo: PhotoInput,
        hints: PlayerHints,
    ) -> VisionStateProposal:
        """
        Deterministic stub processing for MVP testing.

        Returns partial results + uncertainties based on hints.
        """
        players = []
        uncertainties = []

        # If no player positions given, create uncertainty
        if not hints.player_positions:
            uncertainties.append(
                UncertainZone(
                    zone_id="players",
                    zone_type="player_detection",
                    uncertainty_type="missing_data",
                    question="Could not detect player areas. How many players are playing?",
                    alternatives=[2, 3, 4],
                )
            )
        else:
            # Build detected players from hints
            for player_id, position in hints.player_positions.items():
                board_piles = {}

                # For each color, either use known card or create uncertainty
                for color in ["red", "yellow", "green", "blue", "purple"]:
                    key = f"{player_id}_{color}"

                    if key in hints.known_top_cards:
                        # User already told us the top card
                        card_id = hints.known_top_cards[key]
                        board_piles[color] = DetectedZone(
                            zone_type="board_pile",
                            player_id=player_id,
                            color=color,
                            cards=[
                                DetectedCard(
                                    detected_name=card_id,
                                    matched_card_id=card_id,
                                    confidence=ConfidenceLevel.HIGH,
                                    confidence_score=1.0,
                                )
                            ],
                            splay_direction=self._parse_splay(
                                hints.known_splays.get(key, "none")
                            ),
                            card_count=1,
                            card_count_approximate=False,
                            confidence=ConfidenceLevel.HIGH,
                        )
                    elif self.config.stub_cards.get(color):
                        # Use stub cards with medium confidence
                        stub_card = self.config.stub_cards[color][0]
                        board_piles[color] = DetectedZone(
                            zone_type="board_pile",
                            player_id=player_id,
                            color=color,
                            cards=[
                                DetectedCard(
                                    detected_name=stub_card,
                                    matched_card_id=stub_card,
                                    confidence=ConfidenceLevel.MEDIUM,
                                    confidence_score=0.7,
                                )
                            ],
                            splay_direction=SplayDirectionDetected.NONE,
                            card_count=1,
                            card_count_approximate=True,
                            confidence=ConfidenceLevel.MEDIUM,
                        )
                        # Add uncertainty for this pile
                        uncertainties.append(
                            UncertainZone(
                                zone_id=f"{player_id}_board_{color}",
                                zone_type="board_pile",
                                uncertainty_type="card_identity",
                                question=f"What is the top card of {player_id}'s {color} pile?",
                                player_id=player_id,
                                detected_value=stub_card,
                                alternatives=self.config.stub_cards.get(color, []),
                            )
                        )

                # Build detected player
                players.append(
                    DetectedPlayer(
                        player_id=player_id,
                        player_position=position,
                        board_piles=board_piles,
                        score_pile=None,
                        score_pile_count=0,
                        achievements=[],
                        hand=None,
                        hand_count=hints.known_hands.get(player_id, []) and len(hints.known_hands[player_id]) or None,
                        hand_declared=player_id in hints.known_hands,
                    )
                )

        # Stub deck sizes
        deck_sizes = {}
        for age in range(1, 11):
            deck_sizes[str(age)] = max(0, 10 - age)  # Decreasing by age

        # Calculate confidence
        confidence = self._calculate_confidence(players, uncertainties)

        return VisionStateProposal(
            proposal_id=proposal_id,
            timestamp=timestamp,
            confidence_score=confidence,
            confidence_level=self._score_to_level(confidence),
            players=players,
            achievements_available=self._stub_achievements(),
            deck_sizes=deck_sizes,
            uncertain_zones=uncertainties,
            photo_path=photo.image_path if hasattr(photo, 'image_path') else None,
        )

    def _stub_achievements(self) -> list[DetectedCard]:
        """Return stub achievements for testing."""
        achievements = []
        for age in range(1, 10):
            achievements.append(
                DetectedCard(
                    detected_age=age,
                    detected_name=f"achievement_{age}",
                    matched_card_id=f"achievement_{age}",
                    confidence=ConfidenceLevel.HIGH,
                    confidence_score=0.95,
                )
            )
        return achievements

    def _parse_splay(self, direction: str) -> SplayDirectionDetected:
        """Parse splay direction string."""
        direction_map = {
            "none": SplayDirectionDetected.NONE,
            "left": SplayDirectionDetected.LEFT,
            "right": SplayDirectionDetected.RIGHT,
            "up": SplayDirectionDetected.UP,
        }
        return direction_map.get(direction.lower(), SplayDirectionDetected.UNKNOWN)

    def supports_format(self, format: str) -> bool:
        return format.lower() in {"jpg", "jpeg", "png", "webp"}

    def _detect_players(self, photo: PhotoInput, hints: PlayerHints) -> list[DetectedPlayer]:
        """
        Detect player areas and their board states.

        Uses hints if available, otherwise returns empty.
        """
        if hints.player_positions:
            players = []
            for player_id, position in hints.player_positions.items():
                players.append(
                    DetectedPlayer(
                        player_id=player_id,
                        player_position=position,
                        board_piles={},
                        score_pile=None,
                        achievements=[],
                    )
                )
            return players
        return []

    def _detect_achievements(self, photo: PhotoInput) -> list[DetectedCard]:
        """Detect available achievements."""
        return []

    def _detect_deck_sizes(self, photo: PhotoInput) -> dict[str, int]:
        """Detect approximate deck sizes."""
        return {}

    def _identify_uncertainties(
        self,
        players: list[DetectedPlayer],
        achievements: list[DetectedCard],
        hints: PlayerHints,
    ) -> list[UncertainZone]:
        """Identify zones where we're uncertain and need user input."""
        uncertainties = []

        if not players:
            uncertainties.append(
                UncertainZone(
                    zone_id="players",
                    zone_type="player_detection",
                    uncertainty_type="missing_data",
                    question="Could not detect player areas. How many players are playing?",
                    alternatives=[2, 3, 4],
                )
            )

        return uncertainties

    def _calculate_confidence(
        self,
        players: list[DetectedPlayer],
        uncertainties: list[UncertainZone],
    ) -> float:
        """Calculate overall confidence score."""
        if not players:
            return 0.1

        if uncertainties:
            # More uncertainties = lower confidence
            base = 0.8
            penalty = len(uncertainties) * 0.1
            return max(0.3, base - penalty)

        return 0.9

    def _score_to_level(self, score: float) -> ConfidenceLevel:
        """Convert numeric score to confidence level."""
        if score >= 0.9:
            return ConfidenceLevel.HIGH
        elif score >= 0.6:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.3:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.UNCERTAIN
