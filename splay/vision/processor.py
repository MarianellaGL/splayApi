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


class InnovationVisionProcessor(VisionProcessor):
    """
    Vision processor specialized for Innovation.

    STUB: CV implementation deferred.
    Interface is complete for integration.

    For MVP, this detects:
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

        STUB: Real implementation would:
        1. Preprocess image
        2. Detect card regions
        3. Classify cards by age/color
        4. Detect splay directions
        5. Build proposal
        """
        proposal_id = str(uuid.uuid4())
        timestamp = photo.timestamp or time.time()

        # STUB: For now, return empty proposal with uncertainties
        # indicating we need user input

        players = self._detect_players(photo)
        achievements = self._detect_achievements(photo)
        deck_sizes = self._detect_deck_sizes(photo)
        uncertainties = self._identify_uncertainties(players, achievements)

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

    def supports_format(self, format: str) -> bool:
        return format.lower() in {"jpg", "jpeg", "png", "webp"}

    def _detect_players(self, photo: PhotoInput) -> list[DetectedPlayer]:
        """
        Detect player areas and their board states.

        STUB: Returns empty for now.
        Real implementation would use object detection.
        """
        # If player positions are known from hints, use those
        if photo.player_positions:
            players = []
            for player_id, position in photo.player_positions.items():
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
        """
        Detect available achievements.

        STUB: Returns empty for now.
        """
        return []

    def _detect_deck_sizes(self, photo: PhotoInput) -> dict[str, int]:
        """
        Detect approximate deck sizes.

        STUB: Returns empty for now.
        Real implementation would estimate pile heights.
        """
        return {}

    def _identify_uncertainties(
        self,
        players: list[DetectedPlayer],
        achievements: list[DetectedCard],
    ) -> list[UncertainZone]:
        """
        Identify zones where we're uncertain and need user input.
        """
        uncertainties = []

        # If we detected no players, that's uncertain
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
            return 0.5 - (len(uncertainties) * 0.1)

        return 0.8

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
