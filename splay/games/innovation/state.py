"""
Innovation State - Game-specific state model.

Extends the generic GameState with Innovation-specific
structures and computations.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ...engine_core.state import (
    GameState,
    PlayerState,
    Zone,
    ZoneStack,
    Card,
    GamePhase,
    SplayDirection,
)
from .icons import Icon, count_icons

if TYPE_CHECKING:
    from ...spec_schema import GameSpec


# Innovation colors
COLORS = ["red", "yellow", "green", "blue", "purple"]

# Ages 1-10
AGES = list(range(1, 11))

# Win condition: achievements needed
ACHIEVEMENTS_TO_WIN = {
    2: 6,  # 2 players: 6 achievements
    3: 5,  # 3 players: 5 achievements
    4: 4,  # 4 players: 4 achievements
}


@dataclass
class InnovationPlayer(PlayerState):
    """
    Innovation-specific player state.

    Adds:
    - Icon count caching
    - Score computation
    - Age computation
    """

    def compute_score(self, spec: "GameSpec") -> int:
        """Compute total score from score pile."""
        total = 0
        for card in self.score_pile.cards:
            card_def = spec.get_card(card.card_id)
            if card_def and card_def.age:
                total += card_def.age
        return total

    def compute_highest_age(self, spec: "GameSpec") -> int:
        """Compute highest age among top cards on board."""
        max_age = 0
        for color, stack in self.board.items():
            if stack.top_card:
                card_def = spec.get_card(stack.top_card.card_id)
                if card_def and card_def.age and card_def.age > max_age:
                    max_age = card_def.age
        return max_age

    def count_icons(self, spec: "GameSpec") -> dict[Icon, int]:
        """Count all visible icons."""
        return count_icons(self, spec)

    def can_achieve(self, achievement_age: int, spec: "GameSpec") -> bool:
        """Check if player can claim an achievement."""
        score = self.compute_score(spec)
        highest_age = self.compute_highest_age(spec)
        required_score = achievement_age * 5
        return score >= required_score and highest_age >= achievement_age

    @classmethod
    def create(cls, player_id: str, name: str, is_human: bool = True) -> InnovationPlayer:
        """Factory to create a new Innovation player."""
        return cls(
            player_id=player_id,
            name=name,
            is_human=is_human,
            hand=Zone(name="hand"),
            score_pile=Zone(name="score_pile"),
            achievements=Zone(name="achievements"),
            board={color: ZoneStack() for color in COLORS},
        )


@dataclass
class InnovationState(GameState):
    """
    Innovation-specific game state.

    Adds:
    - Age-based deck structure
    - Special achievements
    - Turn structure (2 actions per turn, except turn 1)
    """

    def check_win_condition(self) -> str | None:
        """
        Check if someone has won.

        Returns winner's player_id or None.
        """
        target = ACHIEVEMENTS_TO_WIN.get(self.num_players, 6)

        for player in self.players:
            if player.achievements.count >= target:
                return player.player_id

        # Check deck exhaustion
        highest_empty = 0
        for age in AGES:
            deck_key = f"age_{age}"
            deck = self.supply_decks.get(deck_key)
            if deck and deck.is_empty:
                highest_empty = age

        if highest_empty >= 10:
            # Game ends - highest score wins
            best_score = -1
            winner = None
            for player in self.players:
                if isinstance(player, InnovationPlayer):
                    score = player.compute_score(self.spec) if hasattr(self, '_spec') else 0
                else:
                    score = len(player.score_pile.cards)
                if score > best_score:
                    best_score = score
                    winner = player.player_id
            return winner

        return None

    @classmethod
    def create(
        cls,
        game_id: str,
        spec_id: str,
        player_names: list[tuple[str, str, bool]],  # (id, name, is_human)
    ) -> InnovationState:
        """
        Factory to create a new Innovation game state.

        player_names: list of (player_id, display_name, is_human)
        """
        players = [
            InnovationPlayer.create(pid, name, is_human)
            for pid, name, is_human in player_names
        ]

        # Create age decks (empty - will be filled during setup)
        supply_decks = {f"age_{age}": Zone(name=f"age_{age}") for age in AGES}

        # Create achievements (will be filled during setup)
        achievements = Zone(name="achievements")
        special_achievements = Zone(name="special_achievements")

        return cls(
            game_id=game_id,
            spec_id=spec_id,
            phase=GamePhase.SETUP,
            turn_number=0,
            current_player_idx=0,
            actions_remaining=1,  # Turn 1: only 1 action
            players=players,
            supply_decks=supply_decks,
            achievements=achievements,
            special_achievements=special_achievements,
        )


def setup_innovation_game(
    state: InnovationState,
    spec: "GameSpec",
    random_seed: int = 0,
) -> InnovationState:
    """
    Set up an Innovation game.

    This would normally shuffle decks and deal initial cards.
    For the photo-driven MVP, this is optional since state
    comes from vision.

    STUB: Implement full setup for testing/simulation.
    """
    import random
    rng = random.Random(random_seed)

    # STUB: Full implementation would:
    # 1. Create card instances from spec
    # 2. Shuffle into age decks
    # 3. Create achievements (one per age 1-9)
    # 4. Deal initial hands (2 cards each from age 1)
    # 5. Each player melds 1 card

    return state._copy_with(
        phase=GamePhase.PLAYING,
        random_seed=random_seed,
    )
