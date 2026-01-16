"""
Reducer - Applies actions to game state.

The reducer is the single point of state mutation.
All state changes must go through apply_action().

Design principles:
- Pure function: (state, action) -> new_state
- Validates before applying
- Returns ActionResult with success/failure
- Delegates complex effects to EffectResolver
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .state import GameState, GamePhase, PlayerState, Zone, Card
from .action import Action, ActionType, ActionResult

if TYPE_CHECKING:
    from ..spec_schema import GameSpec


@dataclass
class Reducer:
    """
    Reducer applies actions to game state.

    Stateless - all state is in GameState.
    Spec provides rules for validation.
    """
    spec: GameSpec

    def apply(self, state: GameState, action: Action) -> ActionResult:
        """
        Apply an action to the game state.

        Returns ActionResult with new state or error.
        """
        # Validate action is legal
        validation_error = self._validate_action(state, action)
        if validation_error:
            return ActionResult.failure(validation_error, error_code="INVALID_ACTION")

        # Dispatch to handler based on action type
        handler = self._get_handler(action.action_type)
        if not handler:
            return ActionResult.failure(
                f"No handler for action type: {action.action_type}",
                error_code="NO_HANDLER",
            )

        try:
            result = handler(state, action)
            # Log action to history if successful
            if result.success and result.new_state:
                result.new_state.action_history.append(action)
            return result
        except Exception as e:
            return ActionResult.failure(str(e), error_code="HANDLER_ERROR")

    def _validate_action(self, state: GameState, action: Action) -> str | None:
        """
        Validate that an action is legal in the current state.

        Returns error message if invalid, None if valid.
        """
        # Game phase checks
        if state.phase == GamePhase.GAME_OVER:
            if action.action_type not in {ActionType.VISION_UPDATE, ActionType.USER_CORRECTION}:
                return "Game is over - no actions allowed"

        if state.phase == GamePhase.SETUP:
            if action.action_type not in {
                ActionType.SETUP_GAME,
                ActionType.VISION_UPDATE,
                ActionType.USER_CORRECTION,
            }:
                return "Game not started - only setup actions allowed"

        # Player turn checks for player actions
        player_actions = {
            ActionType.DRAW,
            ActionType.MELD,
            ActionType.DOGMA,
            ActionType.ACHIEVE,
            ActionType.PASS,
            ActionType.CHOOSE,
        }
        if action.action_type in player_actions:
            if action.payload.player_id != state.current_player.player_id:
                # Unless it's a choice during effect resolution
                if action.action_type != ActionType.CHOOSE:
                    return f"Not {action.payload.player_id}'s turn"

            if state.actions_remaining <= 0 and action.action_type != ActionType.CHOOSE:
                return "No actions remaining this turn"

        return None

    def _get_handler(self, action_type: ActionType):
        """Get the handler function for an action type."""
        handlers = {
            ActionType.DRAW: self._handle_draw,
            ActionType.MELD: self._handle_meld,
            ActionType.DOGMA: self._handle_dogma,
            ActionType.ACHIEVE: self._handle_achieve,
            ActionType.PASS: self._handle_pass,
            ActionType.CHOOSE: self._handle_choose,
            ActionType.START_TURN: self._handle_start_turn,
            ActionType.END_TURN: self._handle_end_turn,
            ActionType.VISION_UPDATE: self._handle_vision_update,
            ActionType.USER_CORRECTION: self._handle_user_correction,
        }
        return handlers.get(action_type)

    def _handle_draw(self, state: GameState, action: Action) -> ActionResult:
        """Handle draw action."""
        player_id = action.payload.player_id
        player = state.get_player(player_id)
        if not player:
            return ActionResult.failure(f"Player {player_id} not found")

        # Determine which age to draw from
        age = action.payload.params.get("age")
        if age is None:
            # Draw from highest age with cards
            # STUB: Need to implement age calculation from board
            age = self._calculate_draw_age(state, player)

        deck_key = f"age_{age}"
        deck = state.supply_decks.get(deck_key)

        if not deck or deck.is_empty:
            # Try higher ages
            for try_age in range(age + 1, 11):  # Innovation goes to age 10
                deck_key = f"age_{try_age}"
                deck = state.supply_decks.get(deck_key)
                if deck and not deck.is_empty:
                    break
            else:
                # No cards left - game end condition
                return ActionResult.failure("No cards to draw - game should end")

        # Draw the card
        if deck.cards:
            card = deck.cards[0]
            new_deck = Zone(name=deck.name, cards=deck.cards[1:])

            # Add to player's hand
            new_hand = player.hand.add(card)
            new_player = PlayerState(
                player_id=player.player_id,
                name=player.name,
                is_human=player.is_human,
                hand=new_hand,
                score_pile=player.score_pile,
                achievements=player.achievements,
                board=player.board,
            )

            new_state = state.with_player(new_player).with_deck(deck_key, new_deck)
            new_state = new_state._copy_with(actions_remaining=state.actions_remaining - 1)

            return ActionResult.success_with_state(
                new_state,
                changes=[f"{player.name} drew a card from age {age}"],
                instructions=[f"Draw the top card from the Age {age} deck"],
            )

        return ActionResult.failure("Deck is empty")

    def _handle_meld(self, state: GameState, action: Action) -> ActionResult:
        """Handle meld action."""
        player_id = action.payload.player_id
        card_id = action.payload.card_id
        player = state.get_player(player_id)

        if not player:
            return ActionResult.failure(f"Player {player_id} not found")

        # Find card in hand
        card = None
        for c in player.hand.cards:
            if c.card_id == card_id:
                card = c
                break

        if not card:
            return ActionResult.failure(f"Card {card_id} not in hand")

        # Get card definition to find color
        card_def = self.spec.get_card(card_id)
        if not card_def or not card_def.color:
            return ActionResult.failure(f"Card {card_id} has no color defined")

        color = card_def.color

        # Remove from hand
        new_hand = player.hand.remove(card)

        # Add to board stack
        stack = player.get_board_stack(color)
        new_stack = stack.add_top(card)
        new_player = PlayerState(
            player_id=player.player_id,
            name=player.name,
            is_human=player.is_human,
            hand=new_hand,
            score_pile=player.score_pile,
            achievements=player.achievements,
            board={**player.board, color: new_stack},
        )

        new_state = state.with_player(new_player)
        new_state = new_state._copy_with(actions_remaining=state.actions_remaining - 1)

        return ActionResult.success_with_state(
            new_state,
            changes=[f"{player.name} melded {card_def.name} to {color}"],
            instructions=[f"Place {card_def.name} on top of your {color} pile"],
        )

    def _handle_dogma(self, state: GameState, action: Action) -> ActionResult:
        """
        Handle dogma action.

        This is complex - delegates to EffectResolver.
        STUB: Full implementation in effect_resolver.py
        """
        player_id = action.payload.player_id
        card_id = action.payload.card_id

        # Validate card is on top of a pile
        player = state.get_player(player_id)
        if not player:
            return ActionResult.failure(f"Player {player_id} not found")

        # Find the card on top of a stack
        found = False
        for color, stack in player.board.items():
            if stack.top_card and stack.top_card.card_id == card_id:
                found = True
                break

        if not found:
            return ActionResult.failure(f"Card {card_id} is not on top of any pile")

        # Get card effects
        card_def = self.spec.get_card(card_id)
        if not card_def:
            return ActionResult.failure(f"Card definition for {card_id} not found")

        # STUB: Queue effects for resolution
        # In full implementation, this creates EffectContext and queues it
        new_state = state._copy_with(actions_remaining=state.actions_remaining - 1)

        return ActionResult.success_with_state(
            new_state,
            changes=[f"{player.name} activated dogma on {card_def.name}"],
            instructions=[f"Execute the dogma effect of {card_def.name}"],
        )

    def _handle_achieve(self, state: GameState, action: Action) -> ActionResult:
        """Handle achieve action."""
        player_id = action.payload.player_id
        achievement_id = action.payload.card_id

        player = state.get_player(player_id)
        if not player:
            return ActionResult.failure(f"Player {player_id} not found")

        # Check achievement is available
        achievement_card = None
        for card in state.achievements.cards:
            if card.card_id == achievement_id:
                achievement_card = card
                break

        if not achievement_card:
            return ActionResult.failure(f"Achievement {achievement_id} not available")

        # STUB: Check achievement requirements (score >= age * 5, have card of that age)
        # For now, just allow it

        # Move achievement to player
        new_shared_achievements = state.achievements.remove(achievement_card)
        new_player_achievements = player.achievements.add(achievement_card)

        new_player = PlayerState(
            player_id=player.player_id,
            name=player.name,
            is_human=player.is_human,
            hand=player.hand,
            score_pile=player.score_pile,
            achievements=new_player_achievements,
            board=player.board,
        )

        new_state = state.with_player(new_player)
        new_state = new_state._copy_with(
            achievements=new_shared_achievements,
            actions_remaining=state.actions_remaining - 1,
        )

        return ActionResult.success_with_state(
            new_state,
            changes=[f"{player.name} claimed achievement {achievement_id}"],
            instructions=[f"Take the Age {achievement_id} achievement card"],
        )

    def _handle_pass(self, state: GameState, action: Action) -> ActionResult:
        """Handle pass action (skip remaining actions)."""
        new_state = state._copy_with(actions_remaining=0)
        return ActionResult.success_with_state(
            new_state,
            changes=["Player passed"],
        )

    def _handle_choose(self, state: GameState, action: Action) -> ActionResult:
        """Handle choice response during effect resolution."""
        # STUB: Delegate to effect resolver
        if not state.choice_required:
            return ActionResult.failure("No choice pending")

        # Validate choice is legal
        # Apply choice and continue effect resolution
        return ActionResult.failure("Choice handling not yet implemented")

    def _handle_start_turn(self, state: GameState, action: Action) -> ActionResult:
        """Handle start of turn."""
        new_state = state._copy_with(
            actions_remaining=2,  # Innovation: 2 actions per turn
            phase=GamePhase.PLAYING,
        )
        return ActionResult.success_with_state(
            new_state,
            changes=[f"Turn {state.turn_number + 1} started for {state.current_player.name}"],
        )

    def _handle_end_turn(self, state: GameState, action: Action) -> ActionResult:
        """Handle end of turn, advance to next player."""
        next_player_idx = (state.current_player_idx + 1) % state.num_players
        new_state = state._copy_with(
            current_player_idx=next_player_idx,
            turn_number=state.turn_number + 1,
            actions_remaining=0,
        )
        return ActionResult.success_with_state(
            new_state,
            changes=[f"Turn ended. Next player: {new_state.current_player.name}"],
        )

    def _handle_vision_update(self, state: GameState, action: Action) -> ActionResult:
        """
        Handle state update from vision system.

        This reconciles the detected state with canonical state.
        """
        proposal = action.payload.vision_proposal
        if not proposal:
            return ActionResult.failure("No vision proposal provided")

        # STUB: Reconciliation logic
        # 1. Compare proposal to current state
        # 2. Identify changes
        # 3. Validate changes are legal
        # 4. Apply valid changes
        # 5. Flag uncertain zones for user confirmation

        return ActionResult.failure("Vision update not yet implemented")

    def _handle_user_correction(self, state: GameState, action: Action) -> ActionResult:
        """Handle manual state correction from user."""
        corrections = action.payload.corrections
        if not corrections:
            return ActionResult.failure("No corrections provided")

        # STUB: Apply corrections to state
        # This is a privileged operation - user is authoritative

        return ActionResult.failure("User correction not yet implemented")

    def _calculate_draw_age(self, state: GameState, player: PlayerState) -> int:
        """Calculate which age to draw from based on board state."""
        # STUB: Should look at highest top card age on player's board
        max_age = 1
        for color, stack in player.board.items():
            if stack.top_card:
                card_def = self.spec.get_card(stack.top_card.card_id)
                if card_def and card_def.age and card_def.age > max_age:
                    max_age = card_def.age
        return max_age


def apply_action(spec: GameSpec, state: GameState, action: Action) -> ActionResult:
    """
    Convenience function to apply an action.

    Creates a Reducer and applies the action.
    """
    reducer = Reducer(spec=spec)
    return reducer.apply(state, action)
