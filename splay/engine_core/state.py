"""
Game State - Generic state container that can be specialized per game.

Design principles:
- Immutable-friendly: all mutations return new state
- Serializable: can be saved/loaded for replays
- Observable: state changes can be tracked
- Game-agnostic: Innovation-specific state inherits from this
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from copy import deepcopy
from enum import Enum


class GamePhase(Enum):
    """High-level game phases."""
    SETUP = "setup"
    PLAYING = "playing"
    GAME_OVER = "game_over"


class SplayDirection(Enum):
    """Splay directions for card stacks (Innovation-specific, but generic enough)."""
    NONE = "none"
    LEFT = "left"
    RIGHT = "right"
    UP = "up"


@dataclass
class Card:
    """
    A card instance in the game.

    Note: This is a runtime instance, not the definition.
    The definition lives in GameSpec.cards.
    """
    card_id: str  # References CardDefinition.id in the spec
    instance_id: str  # Unique instance ID (for games with duplicate cards)

    def __hash__(self):
        return hash(self.instance_id)

    def __eq__(self, other):
        if not isinstance(other, Card):
            return False
        return self.instance_id == other.instance_id


@dataclass
class ZoneStack:
    """
    A stack of cards, potentially splayed (for Innovation).

    This is a specialized zone for games where cards stack
    and visibility depends on splay direction.
    """
    cards: list[Card] = field(default_factory=list)
    splay_direction: SplayDirection = SplayDirection.NONE

    @property
    def top_card(self) -> Card | None:
        """Get the top card of the stack."""
        return self.cards[-1] if self.cards else None

    @property
    def is_empty(self) -> bool:
        return len(self.cards) == 0

    def add_top(self, card: Card) -> ZoneStack:
        """Return new stack with card added on top."""
        new_cards = self.cards.copy()
        new_cards.append(card)
        return ZoneStack(cards=new_cards, splay_direction=self.splay_direction)

    def add_bottom(self, card: Card) -> ZoneStack:
        """Return new stack with card added on bottom (tuck)."""
        new_cards = [card] + self.cards.copy()
        return ZoneStack(cards=new_cards, splay_direction=self.splay_direction)

    def remove_top(self) -> tuple[Card | None, ZoneStack]:
        """Return (removed card, new stack)."""
        if not self.cards:
            return None, self
        new_cards = self.cards[:-1]
        return self.cards[-1], ZoneStack(cards=new_cards, splay_direction=self.splay_direction)

    def set_splay(self, direction: SplayDirection) -> ZoneStack:
        """Return new stack with different splay direction."""
        return ZoneStack(cards=self.cards.copy(), splay_direction=direction)


@dataclass
class Zone:
    """
    A generic zone that holds cards.

    Can represent: hand, score pile, achievements, deck, etc.
    """
    name: str
    cards: list[Card] = field(default_factory=list)
    ordered: bool = True  # If false, order doesn't matter

    @property
    def count(self) -> int:
        return len(self.cards)

    @property
    def is_empty(self) -> bool:
        return len(self.cards) == 0

    def add(self, card: Card) -> Zone:
        """Return new zone with card added."""
        new_cards = self.cards.copy()
        new_cards.append(card)
        return Zone(name=self.name, cards=new_cards, ordered=self.ordered)

    def remove(self, card: Card) -> Zone:
        """Return new zone with card removed."""
        new_cards = [c for c in self.cards if c.instance_id != card.instance_id]
        return Zone(name=self.name, cards=new_cards, ordered=self.ordered)

    def contains(self, card_id: str) -> bool:
        """Check if zone contains a card with given card_id."""
        return any(c.card_id == card_id for c in self.cards)


@dataclass
class PlayerState:
    """
    State for a single player.

    This is the generic container. Game-specific player state
    should inherit or extend this.
    """
    player_id: str
    name: str
    is_human: bool = True

    # Generic zones
    hand: Zone = field(default_factory=lambda: Zone(name="hand"))
    score_pile: Zone = field(default_factory=lambda: Zone(name="score_pile"))
    achievements: Zone = field(default_factory=lambda: Zone(name="achievements"))

    # For Innovation: board is a dict of color -> ZoneStack
    # Generic games might use a different structure
    board: dict[str, ZoneStack] = field(default_factory=dict)

    # Computed/cached values (for efficiency)
    _icon_counts: dict[str, int] = field(default_factory=dict)
    _score: int = 0

    def get_board_stack(self, color: str) -> ZoneStack:
        """Get the stack for a color, creating if needed."""
        if color not in self.board:
            return ZoneStack()
        return self.board[color]

    def with_board_stack(self, color: str, stack: ZoneStack) -> PlayerState:
        """Return new player state with updated board stack."""
        new_board = self.board.copy()
        new_board[color] = stack
        return PlayerState(
            player_id=self.player_id,
            name=self.name,
            is_human=self.is_human,
            hand=self.hand,
            score_pile=self.score_pile,
            achievements=self.achievements,
            board=new_board,
            _icon_counts=self._icon_counts,
            _score=self._score,
        )


@dataclass
class GameState:
    """
    Complete game state at a point in time.

    This is the canonical state that the engine operates on.
    All state changes go through the reducer.
    """
    game_id: str
    spec_id: str  # Which GameSpec this state is for

    # Game phase
    phase: GamePhase = GamePhase.SETUP
    turn_number: int = 0
    current_player_idx: int = 0
    actions_remaining: int = 0

    # Players
    players: list[PlayerState] = field(default_factory=list)

    # Shared zones
    supply_decks: dict[str, Zone] = field(default_factory=dict)  # age -> deck
    achievements: Zone = field(default_factory=lambda: Zone(name="achievements"))
    special_achievements: Zone = field(default_factory=lambda: Zone(name="special_achievements"))

    # Effect resolution state
    pending_effects: list[Any] = field(default_factory=list)  # EffectContext stack
    choice_required: Any | None = None  # PendingChoice if waiting for input

    # History (for undo, replay, logging)
    action_history: list[Any] = field(default_factory=list)

    # Random seed for determinism
    random_seed: int = 0
    random_state: Any = None  # numpy RandomState or similar

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def current_player(self) -> PlayerState:
        """Get the current player."""
        return self.players[self.current_player_idx]

    @property
    def num_players(self) -> int:
        return len(self.players)

    def get_player(self, player_id: str) -> PlayerState | None:
        """Get player by ID."""
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None

    def with_player(self, player: PlayerState) -> GameState:
        """Return new state with updated player."""
        new_players = [
            player if p.player_id == player.player_id else p
            for p in self.players
        ]
        return self._copy_with(players=new_players)

    def with_deck(self, deck_key: str, deck: Zone) -> GameState:
        """Return new state with updated deck."""
        new_decks = self.supply_decks.copy()
        new_decks[deck_key] = deck
        return self._copy_with(supply_decks=new_decks)

    def _copy_with(self, **kwargs) -> GameState:
        """Create a copy with some fields replaced."""
        return GameState(
            game_id=kwargs.get("game_id", self.game_id),
            spec_id=kwargs.get("spec_id", self.spec_id),
            phase=kwargs.get("phase", self.phase),
            turn_number=kwargs.get("turn_number", self.turn_number),
            current_player_idx=kwargs.get("current_player_idx", self.current_player_idx),
            actions_remaining=kwargs.get("actions_remaining", self.actions_remaining),
            players=kwargs.get("players", self.players),
            supply_decks=kwargs.get("supply_decks", self.supply_decks),
            achievements=kwargs.get("achievements", self.achievements),
            special_achievements=kwargs.get("special_achievements", self.special_achievements),
            pending_effects=kwargs.get("pending_effects", self.pending_effects),
            choice_required=kwargs.get("choice_required", self.choice_required),
            action_history=kwargs.get("action_history", self.action_history),
            random_seed=kwargs.get("random_seed", self.random_seed),
            random_state=kwargs.get("random_state", self.random_state),
            metadata=kwargs.get("metadata", self.metadata),
        )

    def clone(self) -> GameState:
        """Deep copy the state."""
        return deepcopy(self)
