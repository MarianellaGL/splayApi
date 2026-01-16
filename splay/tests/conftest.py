"""
Pytest fixtures for Splay tests.
"""

import pytest
from typing import Generator

from ..spec_schema import GameSpec
from ..engine_core.state import GameState, PlayerState, Zone, ZoneStack, Card, GamePhase
from ..games.innovation.spec import create_innovation_spec
from ..games.innovation.state import InnovationState, InnovationPlayer


@pytest.fixture
def innovation_spec() -> GameSpec:
    """Create Innovation game spec for testing."""
    return create_innovation_spec()


@pytest.fixture
def empty_game_state(innovation_spec: GameSpec) -> GameState:
    """Create an empty game state for testing."""
    return GameState(
        game_id="test_game",
        spec_id="innovation_base",
        phase=GamePhase.SETUP,
    )


@pytest.fixture
def two_player_state(innovation_spec: GameSpec) -> InnovationState:
    """Create a 2-player Innovation game state."""
    state = InnovationState.create(
        game_id="test_game",
        spec_id="innovation_base",
        player_names=[
            ("human", "Human Player", True),
            ("bot1", "Bot 1", False),
        ],
    )

    # Set up decks with some cards
    from ..engine_core.state import Zone, Card

    # Add some cards to age 1 deck
    age_1_cards = [
        Card(card_id="archery", instance_id="archery_1"),
        Card(card_id="writing", instance_id="writing_1"),
        Card(card_id="the_wheel", instance_id="the_wheel_1"),
        Card(card_id="agriculture", instance_id="agriculture_1"),
        Card(card_id="metalworking", instance_id="metalworking_1"),
    ]
    state.supply_decks["age_1"] = Zone(name="age_1", cards=age_1_cards)

    # Add some cards to age 2 deck
    age_2_cards = [
        Card(card_id="calendar", instance_id="calendar_1"),
        Card(card_id="road_building", instance_id="road_building_1"),
    ]
    state.supply_decks["age_2"] = Zone(name="age_2", cards=age_2_cards)

    # Set up achievements
    achievement_cards = [
        Card(card_id="1", instance_id="achieve_1"),
        Card(card_id="2", instance_id="achieve_2"),
        Card(card_id="3", instance_id="achieve_3"),
    ]
    state.achievements = Zone(name="achievements", cards=achievement_cards)

    # Transition to playing
    state = state._copy_with(
        phase=GamePhase.PLAYING,
        actions_remaining=2,
    )

    return state


@pytest.fixture
def state_with_hands(two_player_state: InnovationState, innovation_spec: GameSpec) -> InnovationState:
    """Create state where players have cards in hand."""
    state = two_player_state

    # Give human player some cards
    human = state.get_player("human")
    human_cards = [
        Card(card_id="writing", instance_id="writing_h1"),
        Card(card_id="archery", instance_id="archery_h1"),
    ]
    new_human = PlayerState(
        player_id=human.player_id,
        name=human.name,
        is_human=human.is_human,
        hand=Zone(name="hand", cards=human_cards),
        score_pile=human.score_pile,
        achievements=human.achievements,
        board=human.board,
    )

    # Give bot some cards
    bot = state.get_player("bot1")
    bot_cards = [
        Card(card_id="the_wheel", instance_id="the_wheel_b1"),
    ]
    new_bot = PlayerState(
        player_id=bot.player_id,
        name=bot.name,
        is_human=bot.is_human,
        hand=Zone(name="hand", cards=bot_cards),
        score_pile=bot.score_pile,
        achievements=bot.achievements,
        board=bot.board,
    )

    state = state.with_player(new_human).with_player(new_bot)
    return state
