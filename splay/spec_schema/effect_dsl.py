"""
Effect DSL - Step-Based Effect System

This module defines the DSL for describing card effects and game actions.
Effects are:
- Step-based: broken into atomic operations
- Composable: can reference other effects
- Deterministic: given the same state and choices, produce the same result
- Testable: each step can be unit tested

Key design decisions:
- Player choices are explicit (ChoiceSpec)
- Conditionals use expression strings evaluated by the engine
- Loops/repeats have explicit bounds
- Targets are resolved lazily via TargetSelector
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StepType(Enum):
    """Types of effect steps."""
    # Card movement
    DRAW = "draw"
    MELD = "meld"
    TUCK = "tuck"
    RETURN = "return"
    TRANSFER = "transfer"
    SCORE = "score"

    # Player choices
    CHOOSE_CARD = "choose_card"
    CHOOSE_PLAYER = "choose_player"
    CHOOSE_OPTION = "choose_option"
    CHOOSE_ZONE = "choose_zone"

    # State modification
    SPLAY = "splay"
    ACHIEVE = "achieve"
    SET_VARIABLE = "set_variable"
    INCREMENT = "increment"

    # Control flow
    CONDITIONAL = "conditional"
    FOR_EACH = "for_each"
    REPEAT = "repeat"
    EXECUTE_EFFECT = "execute_effect"

    # Special
    SHARE_BONUS = "share_bonus"  # Innovation-specific: player who shared gets bonus
    DEMAND = "demand"  # Innovation-specific: opponent must do something


class TargetType(Enum):
    """Types of targets for effects."""
    SELF = "self"
    OPPONENT = "opponent"
    ALL_OPPONENTS = "all_opponents"
    ALL_PLAYERS = "all_players"
    PLAYER_WITH_CONDITION = "player_with_condition"
    CARD = "card"
    ZONE = "zone"


@dataclass
class TargetSelector:
    """
    Selects targets for an effect step.

    Examples:
    - TargetSelector(target_type=TargetType.SELF)
    - TargetSelector(target_type=TargetType.ALL_OPPONENTS)
    - TargetSelector(target_type=TargetType.CARD, filter_expr="card.age <= 3")
    """
    target_type: TargetType
    filter_expr: str | None = None  # Expression to filter targets
    order_by: str | None = None  # How to order multiple targets
    limit: int | None = None  # Max number of targets


@dataclass
class Condition:
    """
    A condition that can be evaluated against game state.

    Expression syntax supports:
    - Comparisons: ==, !=, <, >, <=, >=
    - Boolean: and, or, not
    - Accessors: player.score, card.age, zone.count
    - Functions: count(), has(), sum()
    """
    expression: str
    description: str = ""


@dataclass
class ChoiceSpec:
    """
    Specifies a player choice within an effect.

    Used by the engine to:
    1. Generate legal choices
    2. Present choices to player/bot
    3. Validate chosen option
    """
    choice_type: str  # "card", "player", "zone", "option", "number"
    source: str  # Where choices come from: "hand", "board", "all_players", etc.
    filter_expr: str | None = None  # Optional filter on choices
    min_choices: int = 1
    max_choices: int = 1
    optional: bool = False
    prompt: str = ""  # Human-readable prompt


@dataclass
class EffectStep:
    """
    A single atomic step in an effect resolution.

    Design principle: each step should be:
    - Independently testable
    - Deterministic given state + choices
    - Reversible (for undo systems, future feature)
    """
    step_type: StepType
    step_id: str  # Unique within the effect for debugging/logging

    # Target selection
    target: TargetSelector | None = None

    # Parameters (interpretation depends on step_type)
    params: dict[str, Any] = field(default_factory=dict)

    # For choice steps
    choice_spec: ChoiceSpec | None = None

    # For conditional steps
    condition: Condition | None = None
    then_steps: list[EffectStep] = field(default_factory=list)
    else_steps: list[EffectStep] = field(default_factory=list)

    # For loop steps
    loop_variable: str | None = None
    loop_source: str | None = None  # Expression yielding iterable
    loop_steps: list[EffectStep] = field(default_factory=list)
    max_iterations: int | None = None  # Safety bound


@dataclass
class Effect:
    """
    A complete effect that can be resolved by the engine.

    Effects can be:
    - Card effects (dogma, echo)
    - Action effects (draw, meld)
    - Triggered effects (on score, on achievement)

    Effects are resolved step-by-step, with player choices
    injected at choice steps.
    """
    effect_id: str
    name: str
    description: str = ""

    # Effect classification
    effect_type: str = "action"  # "dogma", "demand", "share", "action", "triggered"
    trigger_icon: str | None = None  # For dogma effects: which icon triggers sharing

    # The steps that make up this effect
    steps: list[EffectStep] = field(default_factory=list)

    # Metadata
    source_card_id: str | None = None
    keywords: list[str] = field(default_factory=list)


# ============================================================================
# Factory functions for common effect patterns
# ============================================================================

def draw_step(step_id: str, count: int = 1, age: str | None = None) -> EffectStep:
    """Create a draw step."""
    params = {"count": count}
    if age:
        params["age"] = age
    return EffectStep(
        step_type=StepType.DRAW,
        step_id=step_id,
        target=TargetSelector(target_type=TargetType.SELF),
        params=params,
    )


def meld_step(step_id: str, card_source: str = "choice") -> EffectStep:
    """Create a meld step."""
    return EffectStep(
        step_type=StepType.MELD,
        step_id=step_id,
        target=TargetSelector(target_type=TargetType.SELF),
        params={"card_source": card_source},
    )


def choose_card_step(
    step_id: str,
    source: str,
    filter_expr: str | None = None,
    optional: bool = False,
    prompt: str = "",
) -> EffectStep:
    """Create a choose card step."""
    return EffectStep(
        step_type=StepType.CHOOSE_CARD,
        step_id=step_id,
        choice_spec=ChoiceSpec(
            choice_type="card",
            source=source,
            filter_expr=filter_expr,
            optional=optional,
            prompt=prompt,
        ),
    )


def conditional_step(
    step_id: str,
    condition_expr: str,
    then_steps: list[EffectStep],
    else_steps: list[EffectStep] | None = None,
) -> EffectStep:
    """Create a conditional step."""
    return EffectStep(
        step_type=StepType.CONDITIONAL,
        step_id=step_id,
        condition=Condition(expression=condition_expr),
        then_steps=then_steps,
        else_steps=else_steps or [],
    )


def for_each_step(
    step_id: str,
    loop_var: str,
    source_expr: str,
    steps: list[EffectStep],
    max_iterations: int = 100,
) -> EffectStep:
    """Create a for-each loop step."""
    return EffectStep(
        step_type=StepType.FOR_EACH,
        step_id=step_id,
        loop_variable=loop_var,
        loop_source=source_expr,
        loop_steps=steps,
        max_iterations=max_iterations,
    )


def splay_step(step_id: str, color: str, direction: str) -> EffectStep:
    """Create a splay step (Innovation-specific)."""
    return EffectStep(
        step_type=StepType.SPLAY,
        step_id=step_id,
        target=TargetSelector(target_type=TargetType.SELF),
        params={"color": color, "direction": direction},
    )


def demand_step(step_id: str, inner_steps: list[EffectStep]) -> EffectStep:
    """Create a demand step - opponents must execute inner steps."""
    return EffectStep(
        step_type=StepType.DEMAND,
        step_id=step_id,
        target=TargetSelector(target_type=TargetType.ALL_OPPONENTS),
        loop_steps=inner_steps,  # Reusing loop_steps for demand contents
    )
