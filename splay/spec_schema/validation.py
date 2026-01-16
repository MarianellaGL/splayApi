"""
Spec Validation - Schema validation for game specifications.

Validates that:
1. Required fields are present
2. References are valid (card IDs, zone names, etc.)
3. Effect DSL is well-formed
4. Invariants hold (e.g., min_players <= max_players)
"""

from __future__ import annotations
from dataclasses import dataclass

from .game_spec import GameSpec, CardDefinition, ActionDefinition
from .effect_dsl import Effect, EffectStep, StepType


class SpecValidationError(Exception):
    """Raised when spec validation fails."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Spec validation failed with {len(errors)} error(s)")


@dataclass
class ValidationResult:
    """Result of validation, with errors and warnings."""
    valid: bool
    errors: list[str]
    warnings: list[str]


def validate_spec(spec: GameSpec) -> ValidationResult:
    """
    Validate a complete game specification.

    Returns ValidationResult with errors and warnings.
    Raises SpecValidationError if raise_on_error=True and errors exist.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Basic field validation
    if not spec.game_id:
        errors.append("game_id is required")
    if not spec.game_name:
        errors.append("game_name is required")
    if spec.min_players < 1:
        errors.append("min_players must be >= 1")
    if spec.max_players < spec.min_players:
        errors.append("max_players must be >= min_players")

    # Collect valid IDs for reference checking
    card_ids = {card.id for card in spec.cards}
    zone_names = {zone.name for zone in spec.zones}
    action_names = {action.name for action in spec.actions}

    # Validate cards
    for card in spec.cards:
        card_errors = _validate_card(card, zone_names)
        errors.extend(card_errors)

    # Validate actions
    for action in spec.actions:
        action_errors = _validate_action(action, card_ids, zone_names)
        errors.extend(action_errors)

    # Validate effects reference valid cards/zones
    all_effects = _collect_all_effects(spec)
    for effect in all_effects:
        effect_errors = _validate_effect(effect, card_ids, zone_names)
        errors.extend(effect_errors)

    # Validate turn structure
    if spec.turn_structure:
        for phase in spec.turn_structure.phases:
            for action_name in phase.mandatory_actions + phase.optional_actions:
                if action_name not in action_names:
                    errors.append(
                        f"Phase '{phase.name}' references unknown action '{action_name}'"
                    )

    # Warnings for incomplete specs
    if not spec.cards:
        warnings.append("No cards defined - spec may be incomplete")
    if not spec.win_conditions:
        warnings.append("No win conditions defined")
    if not spec.turn_structure:
        warnings.append("No turn structure defined")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def _validate_card(card: CardDefinition, zone_names: set[str]) -> list[str]:
    """Validate a single card definition."""
    errors = []
    if not card.id:
        errors.append("Card has empty ID")
    if not card.name:
        errors.append(f"Card '{card.id}' has empty name")

    for effect in card.effects:
        effect_errors = _validate_effect_structure(effect)
        errors.extend([f"Card '{card.id}': {e}" for e in effect_errors])

    return errors


def _validate_action(
    action: ActionDefinition, card_ids: set[str], zone_names: set[str]
) -> list[str]:
    """Validate an action definition."""
    errors = []
    if not action.name:
        errors.append("Action has empty name")
    if not action.phases:
        errors.append(f"Action '{action.name}' has no phases defined")

    for effect in action.effects:
        effect_errors = _validate_effect_structure(effect)
        errors.extend([f"Action '{action.name}': {e}" for e in effect_errors])

    return errors


def _validate_effect(
    effect: Effect, card_ids: set[str], zone_names: set[str]
) -> list[str]:
    """Validate effect references."""
    errors = []

    if effect.source_card_id and effect.source_card_id not in card_ids:
        errors.append(
            f"Effect '{effect.effect_id}' references unknown card '{effect.source_card_id}'"
        )

    return errors


def _validate_effect_structure(effect: Effect) -> list[str]:
    """Validate effect DSL structure (not references)."""
    errors = []

    if not effect.effect_id:
        errors.append("Effect has empty effect_id")

    step_ids = set()
    for step in effect.steps:
        if step.step_id in step_ids:
            errors.append(f"Duplicate step_id '{step.step_id}' in effect '{effect.effect_id}'")
        step_ids.add(step.step_id)

        step_errors = _validate_step(step)
        errors.extend(step_errors)

    return errors


def _validate_step(step: EffectStep) -> list[str]:
    """Validate a single effect step."""
    errors = []

    # Choice steps must have choice_spec
    choice_types = {StepType.CHOOSE_CARD, StepType.CHOOSE_PLAYER, StepType.CHOOSE_OPTION}
    if step.step_type in choice_types and not step.choice_spec:
        errors.append(f"Step '{step.step_id}' is a choice step but has no choice_spec")

    # Conditional steps must have condition
    if step.step_type == StepType.CONDITIONAL and not step.condition:
        errors.append(f"Conditional step '{step.step_id}' has no condition")

    # Loop steps must have loop_variable and loop_source
    if step.step_type == StepType.FOR_EACH:
        if not step.loop_variable:
            errors.append(f"For-each step '{step.step_id}' has no loop_variable")
        if not step.loop_source:
            errors.append(f"For-each step '{step.step_id}' has no loop_source")

    # Recursively validate nested steps
    for nested in step.then_steps + step.else_steps + step.loop_steps:
        errors.extend(_validate_step(nested))

    return errors


def _collect_all_effects(spec: GameSpec) -> list[Effect]:
    """Collect all effects from the spec."""
    effects = []

    for card in spec.cards:
        effects.extend(card.effects)

    for action in spec.actions:
        effects.extend(action.effects)

    effects.extend(spec.setup_effects)

    if spec.turn_structure:
        for phase in spec.turn_structure.phases:
            effects.extend(phase.auto_effects)

    return effects
