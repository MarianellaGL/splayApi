"""
Innovation Game Setup - Creates initial game state.

This module handles:
- Creating decks by age
- Shuffling with seed for determinism
- Setting up achievements
- Initial card deal
- First meld selection

The setup follows Innovation base game rules for 2-4 players.
"""

from __future__ import annotations
import random
from typing import TYPE_CHECKING

from ...engine_core.state import (
    GameState,
    PlayerState,
    Card,
    Zone,
    ZoneStack,
    GamePhase,
    SplayDirection,
)
from .cards import INNOVATION_CARDS, get_card_by_id
from .spec import create_innovation_spec

if TYPE_CHECKING:
    from ...spec_schema import GameSpec


def setup_innovation_game(
    num_players: int = 2,
    human_player_name: str = "Player",
    bot_names: list[str] | None = None,
    random_seed: int | None = None,
    spec: GameSpec | None = None,
) -> GameState:
    """
    Set up a new Innovation game.

    Args:
        num_players: Number of players (2-4)
        human_player_name: Name for human player
        bot_names: Names for bot players (defaults to Bot 1, Bot 2, etc.)
        random_seed: Seed for deterministic shuffling
        spec: Game spec (creates default if not provided)

    Returns:
        Initial GameState ready for play
    """
    if num_players < 2 or num_players > 4:
        raise ValueError("Innovation supports 2-4 players")

    # Set up random with seed for determinism
    rng = random.Random(random_seed)

    # Get or create spec
    game_spec = spec or create_innovation_spec()

    # Create players
    players = _create_players(num_players, human_player_name, bot_names)

    # Create and shuffle decks
    supply_decks = _create_supply_decks(rng)

    # Create achievement supply
    achievements = _create_achievements()

    # Create initial game state
    state = GameState(
        game_id=f"innovation_{random_seed or rng.randint(0, 999999)}",
        spec_id=game_spec.game_id,
        phase=GamePhase.SETUP,
        turn_number=0,
        current_player_idx=0,
        actions_remaining=0,
        players=players,
        supply_decks=supply_decks,
        achievements=achievements,
        special_achievements=Zone(name="special_achievements"),
        random_seed=random_seed or 0,
    )

    # Deal initial hands (2 cards each from age 1)
    state = _deal_initial_hands(state, rng)

    # Initial meld phase handled by game loop (player chooses)
    # For now, just mark setup as complete
    state = state._copy_with(phase=GamePhase.PLAYING, actions_remaining=2)

    return state


def _create_players(
    num_players: int,
    human_name: str,
    bot_names: list[str] | None,
) -> list[PlayerState]:
    """Create player states."""
    players = []

    # Human player
    players.append(PlayerState(
        player_id="human",
        name=human_name,
        is_human=True,
        hand=Zone(name="hand"),
        score_pile=Zone(name="score_pile"),
        achievements=Zone(name="achievements"),
        board={
            "red": ZoneStack(),
            "yellow": ZoneStack(),
            "green": ZoneStack(),
            "blue": ZoneStack(),
            "purple": ZoneStack(),
        },
    ))

    # Bot players
    default_bot_names = bot_names or [f"Bot {i}" for i in range(1, num_players)]
    for i in range(1, num_players):
        bot_name = default_bot_names[i - 1] if i - 1 < len(default_bot_names) else f"Bot {i}"
        players.append(PlayerState(
            player_id=f"bot_{i}",
            name=bot_name,
            is_human=False,
            hand=Zone(name="hand"),
            score_pile=Zone(name="score_pile"),
            achievements=Zone(name="achievements"),
            board={
                "red": ZoneStack(),
                "yellow": ZoneStack(),
                "green": ZoneStack(),
                "blue": ZoneStack(),
                "purple": ZoneStack(),
            },
        ))

    return players


def _create_supply_decks(rng: random.Random) -> dict[str, Zone]:
    """Create and shuffle supply decks by age."""
    decks = {}

    # Group cards by age
    cards_by_age: dict[int, list[Card]] = {}
    for innovation_card in INNOVATION_CARDS:
        age = innovation_card.age
        if age not in cards_by_age:
            cards_by_age[age] = []

        # Create card instance
        card = Card(
            card_id=innovation_card.id,
            instance_id=f"{innovation_card.id}_0",
        )
        cards_by_age[age].append(card)

    # Create decks for ages 1-10
    for age in range(1, 11):
        cards = cards_by_age.get(age, [])
        rng.shuffle(cards)
        decks[f"age_{age}"] = Zone(
            name=f"age_{age}",
            cards=cards,
            ordered=True,
        )

    return decks


def _create_achievements() -> Zone:
    """Create achievement supply."""
    # Standard achievements: one per age 1-9
    achievement_cards = []
    for age in range(1, 10):
        card = Card(
            card_id=f"achievement_{age}",
            instance_id=f"achievement_{age}_0",
        )
        achievement_cards.append(card)

    return Zone(
        name="achievements",
        cards=achievement_cards,
        ordered=False,
    )


def _deal_initial_hands(state: GameState, rng: random.Random) -> GameState:
    """Deal 2 age-1 cards to each player."""
    new_state = state

    age_1_deck = new_state.supply_decks.get("age_1")
    if not age_1_deck:
        return new_state

    deck_cards = list(age_1_deck.cards)

    for player in new_state.players:
        cards_to_deal = min(2, len(deck_cards))
        dealt_cards = deck_cards[:cards_to_deal]
        deck_cards = deck_cards[cards_to_deal:]

        new_hand = Zone(
            name="hand",
            cards=player.hand.cards + dealt_cards,
        )
        new_player = PlayerState(
            player_id=player.player_id,
            name=player.name,
            is_human=player.is_human,
            hand=new_hand,
            score_pile=player.score_pile,
            achievements=player.achievements,
            board=player.board,
        )
        new_state = new_state.with_player(new_player)

    # Update deck
    new_deck = Zone(name="age_1", cards=deck_cards, ordered=True)
    new_state = new_state.with_deck("age_1", new_deck)

    return new_state


def get_achievements_to_win(num_players: int) -> int:
    """Get number of achievements needed to win based on player count."""
    # Innovation rules: 6/5/4 achievements for 2/3/4 players
    if num_players == 2:
        return 6
    elif num_players == 3:
        return 5
    else:
        return 4
