"""
Tests for bot action selection and legality.

Tests:
- Bot selects legal actions
- Personality affects selection
- Physical instructions are generated
"""

import pytest

from ..bots import InnovationBot, BotPolicy, RandomPolicy, FirstLegalPolicy
from ..bots.personality import BALANCED, AGGRESSIVE, PERSONALITIES, create_random_personality
from ..bots.evaluator import HeuristicEvaluator, EvaluationWeights
from ..engine_core.action_generator import legal_actions
from ..engine_core.state import Card, Zone, ZoneStack, PlayerState


class TestBotActionLegality:
    """Tests that bots only select legal actions."""

    def test_bot_selects_legal_action(self, state_with_hands, innovation_spec):
        """Bot always selects from legal actions."""
        state = state_with_hands

        # Make it bot's turn
        state = state._copy_with(current_player_idx=1)

        bot = InnovationBot(player_id="bot1", personality=BALANCED)
        legal = legal_actions(innovation_spec, state)

        decision = bot.select_action(state, innovation_spec, legal)

        # Decision action should be in legal actions
        assert decision.action in legal or any(
            a.action_type == decision.action.action_type and
            a.payload.card_id == decision.action.payload.card_id
            for a in legal
        )

    def test_random_bot_selects_legal(self, state_with_hands, innovation_spec):
        """Random bot selects legal actions."""
        state = state_with_hands
        state = state._copy_with(current_player_idx=1)

        bot = RandomPolicy(seed=42)
        legal = legal_actions(innovation_spec, state)

        # Run multiple times to test randomness
        for _ in range(10):
            decision = bot.select_action(state, innovation_spec, legal)
            assert decision.action in legal


class TestBotPersonality:
    """Tests for personality effects on selection."""

    def test_different_personalities_exist(self):
        """All predefined personalities are accessible."""
        assert "balanced" in PERSONALITIES
        assert "aggressive" in PERSONALITIES
        assert "builder" in PERSONALITIES
        assert "rusher" in PERSONALITIES

    def test_random_personality_creation(self):
        """Can create random personalities."""
        personality = create_random_personality(name="Test", seed=42)
        assert personality.name == "Test"
        assert personality.weights is not None

    def test_aggressive_prefers_dogma(self, state_with_hands, innovation_spec):
        """Aggressive personality has higher dogma preference."""
        aggressive = PERSONALITIES["aggressive"]
        balanced = PERSONALITIES["balanced"]

        assert aggressive.action_preferences.get("dogma", 1.0) > \
               balanced.action_preferences.get("dogma", 1.0)

    def test_personality_affects_weights(self):
        """Different personalities have different weights."""
        aggressive = PERSONALITIES["aggressive"]
        builder = PERSONALITIES["builder"]

        # Aggressive cares more about opponents
        assert aggressive.weights.opponent_penalty < builder.weights.opponent_penalty

        # Builder cares more about board
        assert builder.weights.board_coverage > aggressive.weights.board_coverage


class TestBotInstructions:
    """Tests for physical instruction generation."""

    def test_draw_generates_instructions(self, two_player_state, innovation_spec):
        """Draw action generates physical instructions."""
        state = two_player_state
        state = state._copy_with(current_player_idx=1)

        bot = InnovationBot(player_id="bot1")
        legal = legal_actions(innovation_spec, state)

        # Find draw action
        draw_actions = [a for a in legal if a.action_type.value == "draw"]
        if draw_actions:
            from ..engine_core.action import Action
            decision = bot._create_decision(
                draw_actions[0], state, innovation_spec,
                "Test", 0, 1
            )

            assert len(decision.physical_instructions) > 0
            assert any("draw" in i.lower() for i in decision.physical_instructions)

    def test_meld_generates_instructions(self, state_with_hands, innovation_spec):
        """Meld action generates physical instructions."""
        state = state_with_hands
        state = state._copy_with(current_player_idx=1)

        bot = InnovationBot(player_id="bot1")
        legal = legal_actions(innovation_spec, state)

        # Find meld action
        meld_actions = [a for a in legal if a.action_type.value == "meld"]
        if meld_actions:
            decision = bot._create_decision(
                meld_actions[0], state, innovation_spec,
                "Test", 0, 1
            )

            assert len(decision.physical_instructions) > 0


class TestHeuristicEvaluator:
    """Tests for heuristic evaluation."""

    def test_more_achievements_is_better(self, two_player_state, innovation_spec):
        """State with more achievements evaluates higher."""
        state = two_player_state
        evaluator = HeuristicEvaluator()

        # Baseline evaluation
        eval1 = evaluator.evaluate(state, innovation_spec, "human")

        # Give human an achievement
        human = state.get_player("human")
        new_achievements = human.achievements.add(
            Card(card_id="1", instance_id="ach_1")
        )
        new_human = PlayerState(
            player_id=human.player_id,
            name=human.name,
            is_human=human.is_human,
            hand=human.hand,
            score_pile=human.score_pile,
            achievements=new_achievements,
            board=human.board,
        )
        state2 = state.with_player(new_human)

        eval2 = evaluator.evaluate(state2, innovation_spec, "human")

        assert eval2.total_score > eval1.total_score

    def test_higher_score_pile_is_better(self, two_player_state, innovation_spec):
        """State with higher score evaluates better."""
        state = two_player_state
        evaluator = HeuristicEvaluator()

        eval1 = evaluator.evaluate(state, innovation_spec, "human")

        # Add cards to score pile
        human = state.get_player("human")
        scored_card = Card(card_id="calendar", instance_id="scored_1")
        new_score = human.score_pile.add(scored_card)
        new_human = PlayerState(
            player_id=human.player_id,
            name=human.name,
            is_human=human.is_human,
            hand=human.hand,
            score_pile=new_score,
            achievements=human.achievements,
            board=human.board,
        )
        state2 = state.with_player(new_human)

        eval2 = evaluator.evaluate(state2, innovation_spec, "human")

        assert eval2.total_score > eval1.total_score
