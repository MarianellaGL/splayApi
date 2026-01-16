"""
Tests for spec schema validation.

Tests:
- GameSpec creation
- Validation of required fields
- Effect DSL structure validation
"""

import pytest

from ..spec_schema import (
    GameSpec,
    validate_spec,
    SpecValidationError,
)
from ..spec_schema.game_spec import (
    CardDefinition,
    ActionDefinition,
    ZoneDefinition,
    TurnStructure,
    PhaseDefinition,
    PhaseType,
    WinCondition,
    WinConditionType,
)
from ..spec_schema.effect_dsl import (
    Effect,
    EffectStep,
    StepType,
    draw_step,
)


class TestGameSpecCreation:
    """Tests for creating GameSpec objects."""

    def test_minimal_spec(self):
        """Can create a minimal valid spec."""
        spec = GameSpec(
            game_id="test",
            game_name="Test Game",
            version="1.0",
            min_players=2,
            max_players=4,
        )
        assert spec.game_id == "test"
        assert spec.min_players == 2

    def test_spec_with_cards(self):
        """Can create spec with card definitions."""
        card = CardDefinition(
            id="test_card",
            name="Test Card",
            age=1,
            color="red",
            icons={"top_left": "castle"},
        )
        spec = GameSpec(
            game_id="test",
            game_name="Test Game",
            version="1.0",
            min_players=2,
            max_players=4,
            cards=[card],
        )
        assert len(spec.cards) == 1
        assert spec.get_card("test_card") == card

    def test_spec_with_zones(self):
        """Can create spec with zone definitions."""
        zone = ZoneDefinition(
            name="hand",
            owner="player",
            visibility="private",
        )
        spec = GameSpec(
            game_id="test",
            game_name="Test Game",
            version="1.0",
            min_players=2,
            max_players=4,
            zones=[zone],
        )
        assert spec.get_zone("hand") == zone


class TestSpecValidation:
    """Tests for spec validation."""

    def test_valid_spec_passes(self, innovation_spec):
        """Innovation spec passes validation."""
        result = validate_spec(innovation_spec)
        # May have warnings but should be valid
        assert result.valid or len(result.errors) == 0

    def test_empty_game_id_fails(self):
        """Spec with empty game_id fails validation."""
        spec = GameSpec(
            game_id="",
            game_name="Test",
            version="1.0",
            min_players=2,
            max_players=4,
        )
        result = validate_spec(spec)
        assert not result.valid
        assert any("game_id" in e for e in result.errors)

    def test_invalid_player_count_fails(self):
        """Spec with invalid player count fails validation."""
        spec = GameSpec(
            game_id="test",
            game_name="Test",
            version="1.0",
            min_players=5,
            max_players=2,  # Less than min!
        )
        result = validate_spec(spec)
        assert not result.valid
        assert any("max_players" in e for e in result.errors)

    def test_zero_min_players_fails(self):
        """Spec with zero min_players fails validation."""
        spec = GameSpec(
            game_id="test",
            game_name="Test",
            version="1.0",
            min_players=0,
            max_players=4,
        )
        result = validate_spec(spec)
        assert not result.valid

    def test_warnings_for_incomplete_spec(self):
        """Incomplete spec produces warnings."""
        spec = GameSpec(
            game_id="test",
            game_name="Test",
            version="1.0",
            min_players=2,
            max_players=4,
            # No cards, no win conditions, no turn structure
        )
        result = validate_spec(spec)
        assert result.valid  # Valid but with warnings
        assert len(result.warnings) > 0


class TestEffectDSLValidation:
    """Tests for Effect DSL structure validation."""

    def test_effect_with_steps(self):
        """Effect with valid steps validates."""
        effect = Effect(
            effect_id="test_effect",
            name="Test Effect",
            steps=[
                draw_step("draw_1", count=1, age="1"),
            ],
        )
        # Create spec with card using this effect
        card = CardDefinition(
            id="test_card",
            name="Test Card",
            effects=[effect],
        )
        spec = GameSpec(
            game_id="test",
            game_name="Test",
            version="1.0",
            min_players=2,
            max_players=4,
            cards=[card],
        )
        result = validate_spec(spec)
        # Should not have errors about effect structure
        effect_errors = [e for e in result.errors if "effect" in e.lower()]
        assert len(effect_errors) == 0

    def test_duplicate_step_ids_fail(self):
        """Effect with duplicate step IDs fails validation."""
        effect = Effect(
            effect_id="test_effect",
            name="Test Effect",
            steps=[
                draw_step("same_id", count=1),
                draw_step("same_id", count=2),  # Duplicate!
            ],
        )
        card = CardDefinition(
            id="test_card",
            name="Test Card",
            effects=[effect],
        )
        spec = GameSpec(
            game_id="test",
            game_name="Test",
            version="1.0",
            min_players=2,
            max_players=4,
            cards=[card],
        )
        result = validate_spec(spec)
        assert not result.valid
        assert any("duplicate" in e.lower() for e in result.errors)
