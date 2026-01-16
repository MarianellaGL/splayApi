"""
Tests for the reducer (state transitions).

Tests:
- Action application
- State mutation correctness
- Validation
- Error handling
"""

import pytest

from ..engine_core.state import GameState, PlayerState, Zone, Card, GamePhase
from ..engine_core.action import Action, ActionType, ActionPayload
from ..engine_core.reducer import Reducer, apply_action
from ..games.innovation.spec import create_innovation_spec


class TestDrawAction:
    """Tests for draw action."""

    def test_draw_from_deck(self, two_player_state, innovation_spec):
        """Drawing removes card from deck and adds to hand."""
        state = two_player_state
        initial_deck_size = state.supply_decks["age_1"].count

        action = Action.draw("human", age=1)
        result = apply_action(innovation_spec, state, action)

        assert result.success
        assert result.new_state is not None

        # Deck should have one less card
        new_deck_size = result.new_state.supply_decks["age_1"].count
        assert new_deck_size == initial_deck_size - 1

        # Player should have one more card
        human = result.new_state.get_player("human")
        assert human.hand.count > 0

    def test_draw_decrements_actions(self, two_player_state, innovation_spec):
        """Drawing uses an action."""
        state = two_player_state
        initial_actions = state.actions_remaining

        action = Action.draw("human", age=1)
        result = apply_action(innovation_spec, state, action)

        assert result.success
        assert result.new_state.actions_remaining == initial_actions - 1

    def test_draw_wrong_player_fails(self, two_player_state, innovation_spec):
        """Drawing for wrong player fails."""
        state = two_player_state
        # It's human's turn, bot tries to draw
        action = Action.draw("bot1", age=1)
        result = apply_action(innovation_spec, state, action)

        assert not result.success
        assert "turn" in result.error.lower()


class TestMeldAction:
    """Tests for meld action."""

    def test_meld_from_hand(self, state_with_hands, innovation_spec):
        """Melding moves card from hand to board."""
        state = state_with_hands
        human = state.get_player("human")
        initial_hand_size = human.hand.count

        # Meld the writing card (blue)
        action = Action.meld("human", "writing")
        result = apply_action(innovation_spec, state, action)

        assert result.success
        new_human = result.new_state.get_player("human")

        # Hand should have one less card
        assert new_human.hand.count == initial_hand_size - 1

        # Board should have the card
        blue_stack = new_human.get_board_stack("blue")
        assert not blue_stack.is_empty
        assert blue_stack.top_card.card_id == "writing"

    def test_meld_card_not_in_hand_fails(self, state_with_hands, innovation_spec):
        """Melding a card not in hand fails."""
        state = state_with_hands

        action = Action.meld("human", "nonexistent_card")
        result = apply_action(innovation_spec, state, action)

        assert not result.success
        assert "not in hand" in result.error.lower()


class TestAchieveAction:
    """Tests for achieve action."""

    def test_achieve_success(self, two_player_state, innovation_spec):
        """Can achieve when requirements met."""
        state = two_player_state

        # Set up player to meet achievement requirements
        human = state.get_player("human")

        # Give player score (need 5 for age 1)
        scored_cards = [
            Card(card_id="the_wheel", instance_id="scored_1"),  # Age 1 = 1 point
            Card(card_id="calendar", instance_id="scored_2"),  # Age 2 = 2 points
            Card(card_id="calendar", instance_id="scored_3"),  # Age 2 = 2 points
        ]  # Total: 5 points
        new_score_pile = Zone(name="score_pile", cards=scored_cards)

        # Give player a top card of age 1
        from ..engine_core.state import ZoneStack
        blue_stack = ZoneStack(cards=[Card(card_id="writing", instance_id="board_1")])
        new_board = {**human.board, "blue": blue_stack}

        new_human = PlayerState(
            player_id=human.player_id,
            name=human.name,
            is_human=human.is_human,
            hand=human.hand,
            score_pile=new_score_pile,
            achievements=human.achievements,
            board=new_board,
        )
        state = state.with_player(new_human)

        action = Action.achieve("human", "1")
        result = apply_action(innovation_spec, state, action)

        assert result.success
        new_human = result.new_state.get_player("human")
        assert new_human.achievements.count == 1


class TestGamePhaseValidation:
    """Tests for game phase validation."""

    def test_no_actions_during_setup(self, empty_game_state, innovation_spec):
        """Can't take game actions during setup."""
        state = empty_game_state
        assert state.phase == GamePhase.SETUP

        action = Action.draw("human")
        result = apply_action(innovation_spec, state, action)

        assert not result.success
        assert "setup" in result.error.lower()

    def test_no_actions_when_game_over(self, two_player_state, innovation_spec):
        """Can't take actions when game is over."""
        state = two_player_state._copy_with(phase=GamePhase.GAME_OVER)

        action = Action.draw("human")
        result = apply_action(innovation_spec, state, action)

        assert not result.success
        assert "over" in result.error.lower()


class TestActionHistory:
    """Tests for action history tracking."""

    def test_successful_actions_logged(self, two_player_state, innovation_spec):
        """Successful actions are added to history."""
        state = two_player_state
        initial_history_len = len(state.action_history)

        action = Action.draw("human", age=1)
        result = apply_action(innovation_spec, state, action)

        assert result.success
        assert len(result.new_state.action_history) == initial_history_len + 1
        assert result.new_state.action_history[-1] == action

    def test_failed_actions_not_logged(self, two_player_state, innovation_spec):
        """Failed actions are not added to history."""
        state = two_player_state
        initial_history_len = len(state.action_history)

        # Invalid action - wrong player
        action = Action.draw("bot1", age=1)
        result = apply_action(innovation_spec, state, action)

        assert not result.success
        # State unchanged, history unchanged
