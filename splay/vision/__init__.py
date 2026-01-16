"""
Vision Layer - Photo-based state input.

The vision layer is the PRIMARY source of game state.
It processes photos of the physical table and produces
state proposals that the engine validates and reconciles.

Architecture:
    Photo -> VisionProcessor -> VisionStateProposal -> Reconciler -> CanonicalState

The vision layer is NON-AUTHORITATIVE:
- It proposes state based on what it sees
- The engine validates against rules
- The user corrects ambiguities
- The engine owns the canonical state
"""

from .proposal import (
    VisionStateProposal,
    DetectedCard,
    DetectedZone,
    DetectedPlayer,
    ConfidenceLevel,
    UncertainZone,
    SplayDirectionDetected,
    PhotoInput,
)
from .processor import (
    VisionProcessor,
    MockVisionProcessor,
    ManualInputProcessor,
    InnovationVisionProcessor,
    InnovationVisionConfig,
    PlayerHints,
)
from .reconciler import StateReconciler, ReconciliationResult, Conflict

__all__ = [
    "VisionStateProposal",
    "DetectedCard",
    "DetectedZone",
    "DetectedPlayer",
    "ConfidenceLevel",
    "UncertainZone",
    "SplayDirectionDetected",
    "PhotoInput",
    "VisionProcessor",
    "MockVisionProcessor",
    "ManualInputProcessor",
    "InnovationVisionProcessor",
    "InnovationVisionConfig",
    "PlayerHints",
    "StateReconciler",
    "ReconciliationResult",
    "Conflict",
]
