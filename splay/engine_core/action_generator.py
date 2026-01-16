"""
Action Generator - Generates all legal actions from a game state.

The action generator is used by:
1. Bots to enumerate possible moves
2. UI to show available actions
3. Validation (is this action in legal_actions?)

Design: Generates Action objects, not just action types.
This ensures all generated actions are fully specified.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .state import GameState, GamePhase
from .action import Action, ActionType, ActionPayload

if TYPE_CHECKING:
    from ..spec_schema import GameSpec


@dataclass
class ActionGenerator:
    """
    Generates legal actions for the current game state.

    Uses the GameSpec to determine what actions are available
    and validates preconditions.
    """
    spec: GameSpec

    def generate(self, state: GameState) -> list[Action]:
        """
        Generate all legal actions for the current player.

        Returns a list of fully-specified Action objects.
        """
        if state.phase == GamePhase.GAME_OVER:
            return []

        if state.phase == GamePhase.SETUP:
            return self._generate_setup_actions(state)

        # If waiting for a choice, only choice actions are legal
        if state.choice_required:
            return self._generate_choice_actions(state)

        # Normal turn - generate player actions
        current_player = state.current_player

        if state.actions_remaining <= 0:
            # Only end turn is available
            return [
                Action(
                    action_type=ActionType.END_TURN,
                    payload=ActionPayload(player_id=current_player.player_id),
                )
            ]

        actions = []

        # Draw actions
        actions.extend(self._generate_draw_actions(state, current_player.player_id))

        # Meld actions
        actions.extend(self._generate_meld_actions(state, current_player.player_id))

        # Dogma actions
        actions.extend(self._generate_dogma_actions(state, current_player.player_id))

        # Achieve actions
        actions.extend(self._generate_achieve_actions(state, current_player.player_id))

        # Pass action is always available
        actions.append(
            Action(
                action_type=ActionType.PASS,
                payload=ActionPayload(player_id=current_player.player_id),
            )
        )

        return actions

    def generate_for_player(self, state: GameState, player_id: str) -> list[Action]:
        """
        Generate legal actions for a specific player.

        Used when it's not necessarily that player's turn
        (e.g., during effect resolution).
        """
        # Similar to generate() but for specific player
        actions = []
        actions.extend(self._generate_draw_actions(state, player_id))
        actions.extend(self._generate_meld_actions(state, player_id))
        actions.extend(self._generate_dogma_actions(state, player_id))
        actions.extend(self._generate_achieve_actions(state, player_id))
        return actions

    def _generate_setup_actions(self, state: GameState) -> list[Action]:
        """Generate actions available during setup."""
        return [
            Action(
                action_type=ActionType.START_TURN,
                payload=ActionPayload(),
            )
        ]

    def _generate_choice_actions(self, state: GameState) -> list[Action]:
        """Generate actions when a choice is pending."""
        choice = state.choice_required
        if not choice:
            return []

        # STUB: Generate Action.choose() for each valid choice
        # Need to enumerate valid choices from the choice_spec
        return []

    def _generate_draw_actions(self, state: GameState, player_id: str) -> list[Action]:
        """Generate draw actions."""
        player = state.get_player(player_id)
        if not player:
            return []

        # Calculate draw age
        max_age = self._calculate_highest_top_card_age(state, player)

        # Check if any cards are available at or above this age
        for age in range(max_age, 11):
            deck_key = f"age_{age}"
            deck = state.supply_decks.get(deck_key)
            if deck and not deck.is_empty:
                return [Action.draw(player_id, age)]

        # No cards available
        return []

    def _generate_meld_actions(self, state: GameState, player_id: str) -> list[Action]:
        """Generate meld actions - one per card in hand."""
        player = state.get_player(player_id)
        if not player:
            return []

        actions = []
        for card in player.hand.cards:
            actions.append(Action.meld(player_id, card.card_id))

        return actions

    def _generate_dogma_actions(self, state: GameState, player_id: str) -> list[Action]:
        """Generate dogma actions - one per top card on board."""
        player = state.get_player(player_id)
        if not player:
            return []

        actions = []
        for color, stack in player.board.items():
            if stack.top_card:
                # Check if card has dogma effects
                card_def = self.spec.get_card(stack.top_card.card_id)
                if card_def and card_def.effects:
                    actions.append(Action.dogma(player_id, stack.top_card.card_id))

        return actions

    def _generate_achieve_actions(self, state: GameState, player_id: str) -> list[Action]:
        """Generate achieve actions for claimable achievements."""
        player = state.get_player(player_id)
        if not player:
            return []

        actions = []

        # Get player's score
        score = self._calculate_score(player)

        # Get player's highest top card age
        highest_age = self._calculate_highest_top_card_age(state, player)

        # Check each available achievement
        for card in state.achievements.cards:
            card_def = self.spec.get_card(card.card_id)
            if not card_def or card_def.age is None:
                continue

            required_score = card_def.age * 5
            required_age = card_def.age

            if score >= required_score and highest_age >= required_age:
                actions.append(Action.achieve(player_id, card.card_id))

        return actions

    def _calculate_highest_top_card_age(self, state: GameState, player) -> int:
        """Calculate highest age among top cards on player's board."""
        max_age = 1
        for color, stack in player.board.items():
            if stack.top_card:
                card_def = self.spec.get_card(stack.top_card.card_id)
                if card_def and card_def.age and card_def.age > max_age:
                    max_age = card_def.age
        return max_age

    def _calculate_score(self, player) -> int:
        """Calculate player's score from score pile."""
        total = 0
        for card in player.score_pile.cards:
            # STUB: Need spec to get card ages
            # For now, assume each card is worth its age
            total += 1  # Placeholder
        return total


def legal_actions(spec: GameSpec, state: GameState) -> list[Action]:
    """
    Convenience function to get legal actions.

    Creates an ActionGenerator and generates actions.
    """
    generator = ActionGenerator(spec=spec)
    return generator.generate(state)


def is_legal(spec: GameSpec, state: GameState, action: Action) -> bool:
    """Check if a specific action is legal."""
    legal = legal_actions(spec, state)
    # Compare by type and key payload fields
    for a in legal:
        if (
            a.action_type == action.action_type
            and a.payload.player_id == action.payload.player_id
            and a.payload.card_id == action.payload.card_id
        ):
            return True
    return False
