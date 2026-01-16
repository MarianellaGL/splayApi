"""
Engine Core - Deterministic game state management and effect resolution.

The engine is the runtime that:
1. Loads a GameSpec
2. Manages GameState
3. Generates legal actions
4. Applies actions via the reducer
5. Resolves effects step-by-step
"""

from .state import GameState, PlayerState, Zone, ZoneStack
from .action import Action, ActionType, ActionPayload, ActionResult
from .reducer import Reducer, apply_action
from .action_generator import ActionGenerator, legal_actions
from .effect_resolver import EffectResolver, EffectContext, PendingChoice

__all__ = [
    "GameState",
    "PlayerState",
    "Zone",
    "ZoneStack",
    "Action",
    "ActionType",
    "ActionPayload",
    "ActionResult",
    "Reducer",
    "apply_action",
    "ActionGenerator",
    "legal_actions",
    "EffectResolver",
    "EffectContext",
    "PendingChoice",
]
