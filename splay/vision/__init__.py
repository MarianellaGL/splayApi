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
)
from .processor import VisionProcessor
from .reconciler import StateReconciler, ReconciliationResult, Conflict

__all__ = [
    "VisionStateProposal",
    "DetectedCard",
    "DetectedZone",
    "DetectedPlayer",
    "ConfidenceLevel",
    "UncertainZone",
    "VisionProcessor",
    "StateReconciler",
    "ReconciliationResult",
    "Conflict",
]
