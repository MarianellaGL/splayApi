"""Game specification schema - game-agnostic DSL definitions."""

from .game_spec import GameSpec, TurnStructure, ActionDefinition, WinCondition
from .effect_dsl import (
    Effect,
    EffectStep,
    StepType,
    TargetSelector,
    Condition,
    ChoiceSpec,
)
from .validation import validate_spec, SpecValidationError

__all__ = [
    "GameSpec",
    "TurnStructure",
    "ActionDefinition",
    "WinCondition",
    "Effect",
    "EffectStep",
    "StepType",
    "TargetSelector",
    "Condition",
    "ChoiceSpec",
    "validate_spec",
    "SpecValidationError",
]
