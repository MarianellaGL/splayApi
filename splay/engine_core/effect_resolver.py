"""
Effect Resolver - Step-based effect resolution engine.

This module handles the complex logic of resolving card effects,
including:
- Multi-step effects
- Player choices
- Conditional branches
- Demand effects (opponent must act)
- Share bonuses

The resolver maintains an effect stack and processes steps one at a time,
pausing when player input is required.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TYPE_CHECKING

from .state import GameState, PlayerState, Card, Zone, ZoneStack, SplayDirection
from .action import ActionResult
from .expression import ExpressionEvaluator, ExpressionContext

if TYPE_CHECKING:
    from ..spec_schema import GameSpec, Effect, EffectStep
    from ..spec_schema.effect_dsl import StepType, ChoiceSpec


class ResolverState(Enum):
    """State of the effect resolver."""
    READY = "ready"  # No effects pending
    RESOLVING = "resolving"  # Processing effects
    WAITING_CHOICE = "waiting_choice"  # Paused for player input
    COMPLETED = "completed"  # Effect finished
    ERROR = "error"  # Resolution failed


@dataclass
class PendingChoice:
    """
    Represents a choice that must be made by a player.

    This is returned to the UI/bot when the resolver needs input.
    """
    choice_id: str
    player_id: str
    choice_type: str  # "card", "player", "option", etc.
    prompt: str
    options: list[Any]  # Available choices
    min_choices: int = 1
    max_choices: int = 1
    optional: bool = False

    # Context for the choice
    source_effect_id: str | None = None
    source_step_id: str | None = None


@dataclass
class EffectContext:
    """
    Context for resolving an effect.

    Maintains state as we step through the effect,
    including loop counters, resolved choices, and variables.
    """
    effect: Effect
    source_player_id: str
    current_step_index: int = 0
    sub_contexts: list[EffectContext] = field(default_factory=list)

    # Variables set during resolution (e.g., loop variables)
    variables: dict[str, Any] = field(default_factory=dict)

    # Choices made during this effect
    resolved_choices: dict[str, list[str]] = field(default_factory=dict)

    # For demand effects: which opponents have executed
    demand_players_remaining: list[str] = field(default_factory=list)

    # Share tracking
    players_who_shared: list[str] = field(default_factory=list)
    share_bonus_pending: bool = False


@dataclass
class EffectResolver:
    """
    Resolves effects step-by-step.

    The resolver is stateful during resolution but does not
    own the game state - it returns new states.
    """
    spec: GameSpec
    state: ResolverState = ResolverState.READY
    effect_stack: list[EffectContext] = field(default_factory=list)
    pending_choice: PendingChoice | None = None

    def begin_effect(
        self,
        game_state: GameState,
        effect: Effect,
        source_player_id: str,
    ) -> tuple[GameState, PendingChoice | None]:
        """
        Begin resolving an effect.

        Returns (new_state, pending_choice or None).
        """
        context = EffectContext(
            effect=effect,
            source_player_id=source_player_id,
        )

        # For dogma effects, determine sharing
        if effect.effect_type == "dogma" and effect.trigger_icon:
            context = self._setup_sharing(game_state, context, effect.trigger_icon)

        self.effect_stack.append(context)
        self.state = ResolverState.RESOLVING

        return self._continue_resolution(game_state)

    def provide_choice(
        self,
        game_state: GameState,
        choice_id: str,
        chosen_values: list[str],
    ) -> tuple[GameState, PendingChoice | None]:
        """
        Provide a choice to continue resolution.

        Called when the player/bot has made a decision.
        """
        if not self.pending_choice:
            raise ValueError("No choice pending")

        if self.pending_choice.choice_id != choice_id:
            raise ValueError(f"Choice ID mismatch: expected {self.pending_choice.choice_id}")

        # Validate choice
        if not self._validate_choice(chosen_values):
            raise ValueError("Invalid choice")

        # Record choice and continue
        context = self.effect_stack[-1]
        context.resolved_choices[choice_id] = chosen_values
        self.pending_choice = None

        return self._continue_resolution(game_state)

    def _continue_resolution(
        self,
        game_state: GameState,
    ) -> tuple[GameState, PendingChoice | None]:
        """
        Continue resolving effects until complete or choice needed.
        """
        while self.effect_stack:
            context = self.effect_stack[-1]
            effect = context.effect

            # Process steps
            while context.current_step_index < len(effect.steps):
                step = effect.steps[context.current_step_index]
                result = self._resolve_step(game_state, context, step)

                if result.needs_choice:
                    self.state = ResolverState.WAITING_CHOICE
                    self.pending_choice = result.pending_choice
                    return game_state, self.pending_choice

                if result.new_state:
                    game_state = result.new_state

                if result.sub_context:
                    # Push sub-context for nested effects
                    self.effect_stack.append(result.sub_context)
                    break  # Process sub-context first

                context.current_step_index += 1
            else:
                # Effect complete
                self.effect_stack.pop()

                # Check for share bonus
                if context.share_bonus_pending and context.players_who_shared:
                    # Execute share bonus step
                    pass  # STUB: Implement share bonus

        self.state = ResolverState.COMPLETED
        return game_state, None

    def _resolve_step(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """
        Resolve a single effect step.

        Returns StepResult indicating outcome.
        """
        from ..spec_schema.effect_dsl import StepType

        handlers: dict[StepType, Callable] = {
            StepType.DRAW: self._step_draw,
            StepType.MELD: self._step_meld,
            StepType.TUCK: self._step_tuck,
            StepType.RETURN: self._step_return,
            StepType.TRANSFER: self._step_transfer,
            StepType.SCORE: self._step_score,
            StepType.CHOOSE_CARD: self._step_choose_card,
            StepType.CHOOSE_PLAYER: self._step_choose_player,
            StepType.CHOOSE_OPTION: self._step_choose_option,
            StepType.SPLAY: self._step_splay,
            StepType.ACHIEVE: self._step_achieve,
            StepType.CONDITIONAL: self._step_conditional,
            StepType.FOR_EACH: self._step_for_each,
            StepType.DEMAND: self._step_demand,
        }

        handler = handlers.get(step.step_type)
        if not handler:
            return StepResult(error=f"Unknown step type: {step.step_type}")

        return handler(game_state, context, step)

    def _step_draw(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """
        Handle draw step.

        Draws card(s) from supply deck to player's hand.
        If specified deck is empty, draws from next higher age.
        """
        player_id = self._resolve_target_player(context, step)
        player = game_state.get_player(player_id)
        if not player:
            return StepResult(error=f"Player {player_id} not found")

        count = step.params.get("count", 1)
        age = step.params.get("age")
        reveal = step.params.get("reveal", False)

        # Evaluate age expression
        if isinstance(age, str):
            age = self._evaluate_expression(age, context, game_state)

        if age is None:
            # Draw from highest top card age
            age = self._get_highest_top_card_age(game_state, player)

        new_state = game_state
        drawn_cards = []

        for _ in range(count):
            # Find deck with cards
            draw_age = age
            deck = None
            while draw_age <= 10:
                deck_key = f"age_{draw_age}"
                deck = new_state.supply_decks.get(deck_key)
                if deck and not deck.is_empty:
                    break
                draw_age += 1

            if not deck or deck.is_empty:
                # No cards to draw - game ending condition
                context.variables["_no_cards"] = True
                break

            # Draw the card
            card = deck.cards[0]
            new_deck = Zone(name=deck.name, cards=deck.cards[1:])
            drawn_cards.append(card)

            # Store drawn card for later steps
            context.variables["drawn_card"] = card.card_id
            context.variables["last_drawn_age"] = draw_age

            # Add to player's hand
            player = new_state.get_player(player_id)
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

            new_state = new_state.with_player(new_player).with_deck(f"age_{draw_age}", new_deck)

        return StepResult(new_state=new_state)

    def _step_meld(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """
        Handle meld step.

        Moves a card from hand to top of board pile of matching color.
        """
        player_id = self._resolve_target_player(context, step)
        player = game_state.get_player(player_id)
        if not player:
            return StepResult(error=f"Player {player_id} not found")

        # Get card to meld
        card_source = step.params.get("card_source", "choice")
        card_id = step.params.get("card")

        if card_source == "choice" or card_source == "chosen_card":
            card_id = context.variables.get("chosen_card")
        elif card_source == "drawn_card":
            card_id = context.variables.get("drawn_card")
        elif isinstance(card_id, str) and card_id.startswith("$"):
            # Variable reference
            card_id = context.variables.get(card_id[1:])

        if not card_id:
            return StepResult(error="No card specified for meld")

        # Find card in hand
        card = None
        for c in player.hand.cards:
            if c.card_id == card_id:
                card = c
                break

        if not card:
            return StepResult(error=f"Card {card_id} not in hand")

        # Get card color from spec
        card_def = self.spec.get_card(card_id) if self.spec else None
        if not card_def or not card_def.color:
            return StepResult(error=f"Card {card_id} has no color")

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

        new_state = game_state.with_player(new_player)
        return StepResult(new_state=new_state)

    def _step_tuck(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """
        Handle tuck step (add to bottom of pile).

        Like meld, but card goes under the stack.
        """
        player_id = self._resolve_target_player(context, step)
        player = game_state.get_player(player_id)
        if not player:
            return StepResult(error=f"Player {player_id} not found")

        card_id = step.params.get("card") or context.variables.get("chosen_card")
        if not card_id:
            return StepResult(error="No card specified for tuck")

        # Find card in hand
        card = None
        for c in player.hand.cards:
            if c.card_id == card_id:
                card = c
                break

        if not card:
            return StepResult(error=f"Card {card_id} not in hand")

        # Get card color
        card_def = self.spec.get_card(card_id) if self.spec else None
        if not card_def or not card_def.color:
            return StepResult(error=f"Card {card_id} has no color")

        color = card_def.color

        # Remove from hand
        new_hand = player.hand.remove(card)

        # Add to bottom of board stack
        stack = player.get_board_stack(color)
        new_stack = stack.add_bottom(card)

        new_player = PlayerState(
            player_id=player.player_id,
            name=player.name,
            is_human=player.is_human,
            hand=new_hand,
            score_pile=player.score_pile,
            achievements=player.achievements,
            board={**player.board, color: new_stack},
        )

        new_state = game_state.with_player(new_player)
        return StepResult(new_state=new_state)

    def _step_return(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """
        Handle return step (card back to supply).

        Returns a card to the bottom of its age deck.
        """
        player_id = self._resolve_target_player(context, step)
        player = game_state.get_player(player_id)
        if not player:
            return StepResult(error=f"Player {player_id} not found")

        card_param = step.params.get("card")
        card_id = None

        if card_param == "chosen_card":
            card_id = context.variables.get("chosen_card")
        elif card_param:
            card_id = self._evaluate_expression(card_param, context, game_state)
        else:
            card_id = context.variables.get("chosen_card")

        if not card_id:
            return StepResult(error="No card specified for return")

        # Find card in hand
        card = None
        for c in player.hand.cards:
            if c.card_id == card_id:
                card = c
                break

        if not card:
            return StepResult(error=f"Card {card_id} not in hand")

        # Get card age
        card_def = self.spec.get_card(card_id) if self.spec else None
        age = card_def.age if card_def else 1

        # Store returned card info for later expressions
        context.variables["returned_card"] = {
            "card_id": card_id,
            "age": age,
        }

        # Remove from hand
        new_hand = player.hand.remove(card)

        # Add to bottom of age deck
        deck_key = f"age_{age}"
        deck = game_state.supply_decks.get(deck_key, Zone(name=deck_key))
        new_deck = Zone(name=deck.name, cards=deck.cards + [card])

        new_player = PlayerState(
            player_id=player.player_id,
            name=player.name,
            is_human=player.is_human,
            hand=new_hand,
            score_pile=player.score_pile,
            achievements=player.achievements,
            board=player.board,
        )

        new_state = game_state.with_player(new_player).with_deck(deck_key, new_deck)
        return StepResult(new_state=new_state)

    def _step_transfer(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """
        Handle transfer step (card from one zone to another).

        Supports transferring between players or zones.
        """
        source = step.params.get("source", "hand")
        destination = step.params.get("destination", "opponent_hand")
        selection = step.params.get("selection", "choice")

        # Determine source player and zone
        source_player_id = self._resolve_target_player(context, step)
        source_player = game_state.get_player(source_player_id)
        if not source_player:
            return StepResult(error=f"Source player {source_player_id} not found")

        # Determine destination player
        if "opponent" in destination:
            dest_player_id = context.source_player_id  # Demanding player
        else:
            dest_player_id = self._resolve_target_player(context, step)

        dest_player = game_state.get_player(dest_player_id)
        if not dest_player:
            return StepResult(error=f"Destination player {dest_player_id} not found")

        # Get card to transfer
        card = None
        card_id = None

        if selection == "highest_age":
            # Find highest age card in source zone
            if source == "hand":
                highest_age = -1
                for c in source_player.hand.cards:
                    card_def = self.spec.get_card(c.card_id) if self.spec else None
                    if card_def and card_def.age and card_def.age > highest_age:
                        highest_age = card_def.age
                        card = c
                        card_id = c.card_id
        elif selection == "choice":
            card_id = context.variables.get("chosen_card")
            if card_id:
                for c in source_player.hand.cards:
                    if c.card_id == card_id:
                        card = c
                        break

        if not card:
            return StepResult(new_state=game_state)  # No card to transfer

        # Remove from source
        new_source_hand = source_player.hand.remove(card)
        new_source_player = PlayerState(
            player_id=source_player.player_id,
            name=source_player.name,
            is_human=source_player.is_human,
            hand=new_source_hand,
            score_pile=source_player.score_pile,
            achievements=source_player.achievements,
            board=source_player.board,
        )

        # Add to destination
        new_dest_hand = dest_player.hand.add(card)
        new_dest_player = PlayerState(
            player_id=dest_player.player_id,
            name=dest_player.name,
            is_human=dest_player.is_human,
            hand=new_dest_hand,
            score_pile=dest_player.score_pile,
            achievements=dest_player.achievements,
            board=dest_player.board,
        )

        new_state = game_state.with_player(new_source_player).with_player(new_dest_player)
        return StepResult(new_state=new_state)

    def _step_score(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """
        Handle score step (move card to score pile).

        Card value (age) becomes score points.
        """
        player_id = self._resolve_target_player(context, step)
        player = game_state.get_player(player_id)
        if not player:
            return StepResult(error=f"Player {player_id} not found")

        # Get card to score
        card_param = step.params.get("card")
        card_id = None
        card = None

        if card_param == "drawn_card":
            card_id = context.variables.get("drawn_card")
        elif card_param == "chosen_card":
            card_id = context.variables.get("chosen_card")
        elif card_param:
            card_id = self._evaluate_expression(card_param, context, game_state)
        else:
            card_id = context.variables.get("drawn_card") or context.variables.get("chosen_card")

        if not card_id:
            return StepResult(error="No card specified for score")

        # Find card in hand
        for c in player.hand.cards:
            if c.card_id == card_id:
                card = c
                break

        if not card:
            return StepResult(error=f"Card {card_id} not in hand")

        # Remove from hand
        new_hand = player.hand.remove(card)

        # Add to score pile
        new_score_pile = player.score_pile.add(card)

        # Calculate new score
        new_score = player._score
        card_def = self.spec.get_card(card_id) if self.spec else None
        if card_def and card_def.age:
            new_score += card_def.age

        new_player = PlayerState(
            player_id=player.player_id,
            name=player.name,
            is_human=player.is_human,
            hand=new_hand,
            score_pile=new_score_pile,
            achievements=player.achievements,
            board=player.board,
            _score=new_score,
        )

        new_state = game_state.with_player(new_player)
        return StepResult(new_state=new_state)

    def _step_choose_card(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """Handle choose card step - pauses for player input."""
        choice_spec = step.choice_spec
        if not choice_spec:
            return StepResult(error="Choose card step missing choice_spec")

        player_id = self._resolve_target_player(context, step)

        # Generate available choices
        options = self._get_card_choices(game_state, player_id, choice_spec)

        if not options and choice_spec.optional:
            # Skip if optional and no choices
            return StepResult(new_state=game_state)

        if not options:
            return StepResult(error="No valid choices available")

        pending = PendingChoice(
            choice_id=f"{context.effect.effect_id}_{step.step_id}",
            player_id=player_id,
            choice_type="card",
            prompt=choice_spec.prompt or "Choose a card",
            options=options,
            min_choices=choice_spec.min_choices,
            max_choices=choice_spec.max_choices,
            optional=choice_spec.optional,
            source_effect_id=context.effect.effect_id,
            source_step_id=step.step_id,
        )

        return StepResult(needs_choice=True, pending_choice=pending)

    def _step_choose_player(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """Handle choose player step."""
        # STUB: Similar to choose_card but for players
        return StepResult(new_state=game_state)

    def _step_choose_option(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """Handle choose option step (yes/no, which effect, etc.)."""
        # STUB
        return StepResult(new_state=game_state)

    def _step_splay(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """Handle splay step."""
        player_id = self._resolve_target_player(context, step)
        player = game_state.get_player(player_id)
        if not player:
            return StepResult(error=f"Player {player_id} not found")

        color = step.params.get("color")
        direction_str = step.params.get("direction", "none")

        direction_map = {
            "none": SplayDirection.NONE,
            "left": SplayDirection.LEFT,
            "right": SplayDirection.RIGHT,
            "up": SplayDirection.UP,
        }
        direction = direction_map.get(direction_str, SplayDirection.NONE)

        stack = player.get_board_stack(color)
        if stack.is_empty:
            return StepResult(new_state=game_state)  # Can't splay empty stack

        new_stack = stack.set_splay(direction)
        new_player = player.with_board_stack(color, new_stack)
        new_state = game_state.with_player(new_player)

        return StepResult(new_state=new_state)

    def _step_achieve(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """Handle achieve step (claim achievement via effect)."""
        # STUB
        return StepResult(new_state=game_state)

    def _step_conditional(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """Handle conditional step."""
        condition = step.condition
        if not condition:
            return StepResult(error="Conditional step missing condition")

        result = self._evaluate_condition(condition.expression, context, game_state)

        if result:
            # Create sub-context for then_steps
            sub_effect = Effect(
                effect_id=f"{context.effect.effect_id}_then",
                name="conditional_then",
                steps=step.then_steps,
            )
            sub_context = EffectContext(
                effect=sub_effect,
                source_player_id=context.source_player_id,
                variables=context.variables.copy(),
            )
            return StepResult(sub_context=sub_context)
        elif step.else_steps:
            sub_effect = Effect(
                effect_id=f"{context.effect.effect_id}_else",
                name="conditional_else",
                steps=step.else_steps,
            )
            sub_context = EffectContext(
                effect=sub_effect,
                source_player_id=context.source_player_id,
                variables=context.variables.copy(),
            )
            return StepResult(sub_context=sub_context)

        return StepResult(new_state=game_state)

    def _step_for_each(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """
        Handle for-each loop step.

        Iterates over a collection, executing inner steps for each item.
        """
        loop_var = step.loop_variable or "item"
        loop_source = step.loop_source
        loop_steps = step.loop_steps or []
        max_iterations = step.max_iterations or 100

        # Evaluate loop source to get iterable
        if loop_source == "all_players":
            items = [p.player_id for p in game_state.players]
        elif loop_source == "other_players":
            items = [
                p.player_id for p in game_state.players
                if p.player_id != context.source_player_id
            ]
        else:
            items_val = self._evaluate_expression(loop_source, context, game_state)
            if isinstance(items_val, (list, tuple)):
                items = list(items_val)
            elif hasattr(items_val, "cards"):
                items = [c.card_id for c in items_val.cards]
            else:
                items = []

        if not items or not loop_steps:
            return StepResult(new_state=game_state)

        # Create sub-effect for loop body
        from ..spec_schema.effect_dsl import Effect

        new_state = game_state
        iterations = 0

        for item in items:
            if iterations >= max_iterations:
                break

            # Set loop variable
            context.variables[loop_var] = item

            # If item is a player_id, set it as current target
            if isinstance(item, str) and game_state.get_player(item):
                context.variables["_current_loop_player"] = item

            # Execute loop steps
            sub_effect = Effect(
                effect_id=f"{context.effect.effect_id}_loop_{iterations}",
                name=f"loop_iteration_{iterations}",
                steps=loop_steps,
            )
            sub_context = EffectContext(
                effect=sub_effect,
                source_player_id=context.source_player_id,
                variables=context.variables.copy(),
            )

            # Process steps
            for sub_step in loop_steps:
                result = self._resolve_step(new_state, sub_context, sub_step)
                if result.error:
                    return result
                if result.new_state:
                    new_state = result.new_state
                if result.needs_choice:
                    return result

            iterations += 1

        return StepResult(new_state=new_state)

    def _step_demand(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """
        Handle demand step - opponents must execute inner steps.

        In Innovation, demand effects target opponents with fewer
        of the triggering icon than the demanding player.
        """
        demand_steps = step.loop_steps or []

        if not demand_steps:
            return StepResult(new_state=game_state)

        # Get trigger icon from parent effect
        trigger_icon = context.effect.trigger_icon

        # Get source player's icon count
        source_player = game_state.get_player(context.source_player_id)
        if not source_player:
            return StepResult(error="Source player not found")

        source_icon_count = self._count_icons(game_state, source_player, trigger_icon)

        # Find opponents with fewer icons (they are demanded)
        demanded_players = []
        for player in game_state.players:
            if player.player_id == context.source_player_id:
                continue
            player_icon_count = self._count_icons(game_state, player, trigger_icon)
            if player_icon_count < source_icon_count:
                demanded_players.append(player.player_id)

        if not demanded_players:
            # No one to demand
            return StepResult(new_state=game_state)

        # Store demanded players
        context.demand_players_remaining = demanded_players.copy()

        # Execute demand steps for each demanded player
        from ..spec_schema.effect_dsl import Effect

        new_state = game_state

        for demanded_player_id in demanded_players:
            # Create context for demanded player
            demand_effect = Effect(
                effect_id=f"{context.effect.effect_id}_demand_{demanded_player_id}",
                name=f"demand_{demanded_player_id}",
                steps=demand_steps,
            )
            demand_context = EffectContext(
                effect=demand_effect,
                source_player_id=demanded_player_id,  # Demanded player executes
                variables={
                    **context.variables,
                    "_demanding_player": context.source_player_id,
                },
            )

            # Execute demand steps
            for demand_step in demand_steps:
                # Override target to be the demanded player
                result = self._resolve_step(new_state, demand_context, demand_step)
                if result.error:
                    # Demand steps can fail (e.g., no cards) - continue
                    continue
                if result.new_state:
                    new_state = result.new_state
                if result.needs_choice:
                    # Need to pause for player choice
                    return result

        return StepResult(new_state=new_state)

    def _setup_sharing(
        self,
        game_state: GameState,
        context: EffectContext,
        trigger_icon: str,
    ) -> EffectContext:
        """
        Set up sharing for dogma effects.

        Players with >= icons share in the effect.
        """
        source_player = game_state.get_player(context.source_player_id)
        if not source_player:
            return context

        source_icons = self._count_icons(game_state, source_player, trigger_icon)

        sharing_players = []
        for player in game_state.players:
            if player.player_id == context.source_player_id:
                continue
            player_icons = self._count_icons(game_state, player, trigger_icon)
            if player_icons >= source_icons:
                sharing_players.append(player.player_id)
                context.players_who_shared.append(player.player_id)

        if sharing_players:
            context.share_bonus_pending = True

        return context

    def _count_icons(
        self,
        game_state: GameState,
        player: PlayerState,
        icon: str,
    ) -> int:
        """
        Count visible icons for a player.

        Visibility depends on splay direction:
        - NONE: Only top card icons visible
        - LEFT: Left column of all cards visible
        - RIGHT: Right column of all cards visible
        - UP: Bottom row of all cards visible
        """
        if not icon:
            return 0

        total = 0

        for color, stack in player.board.items():
            if stack.is_empty:
                continue

            cards = stack.cards
            splay = stack.splay_direction

            for i, card in enumerate(cards):
                is_top = (i == len(cards) - 1)
                card_def = self.spec.get_card(card.card_id) if self.spec else None
                if not card_def or not card_def.icons:
                    continue

                # Determine which icons are visible
                visible_positions = []

                if is_top:
                    # Top card - all icons visible
                    visible_positions = list(card_def.icons.keys())
                elif splay == SplayDirection.LEFT:
                    # Left splay - right column visible
                    visible_positions = ["bottom_right"]
                elif splay == SplayDirection.RIGHT:
                    # Right splay - left column visible
                    visible_positions = ["top_left", "bottom_left"]
                elif splay == SplayDirection.UP:
                    # Up splay - bottom row visible
                    visible_positions = ["bottom_left", "bottom_center", "bottom_right"]
                # NONE - only top card visible (handled above)

                for pos in visible_positions:
                    if card_def.icons.get(pos) == icon:
                        total += 1

        return total

    def _get_highest_top_card_age(
        self,
        game_state: GameState,
        player: PlayerState,
    ) -> int:
        """Get the highest age among player's top cards."""
        max_age = 1

        for color, stack in player.board.items():
            if stack.top_card:
                card_def = self.spec.get_card(stack.top_card.card_id) if self.spec else None
                if card_def and card_def.age and card_def.age > max_age:
                    max_age = card_def.age

        return max_age

    def _resolve_target_player(self, context: EffectContext, step: EffectStep) -> str:
        """Resolve which player a step targets."""
        if step.target:
            from ..spec_schema.effect_dsl import TargetType

            if step.target.target_type == TargetType.SELF:
                return context.source_player_id
            # STUB: Handle other target types

        return context.source_player_id

    def _get_card_choices(
        self,
        game_state: GameState,
        player_id: str,
        choice_spec: ChoiceSpec,
    ) -> list[str]:
        """Get available card choices based on choice_spec."""
        player = game_state.get_player(player_id)
        if not player:
            return []

        # Determine source zone
        if choice_spec.source == "hand":
            cards = player.hand.cards
        elif choice_spec.source == "score_pile":
            cards = player.score_pile.cards
        elif choice_spec.source == "board":
            cards = []
            for stack in player.board.values():
                cards.extend(stack.cards)
        else:
            cards = []

        # Apply filter if present
        if choice_spec.filter_expr:
            # STUB: Evaluate filter expression
            pass

        return [c.card_id for c in cards]

    def _evaluate_expression(
        self,
        expr: str,
        context: EffectContext,
        game_state: GameState,
    ) -> Any:
        """Evaluate an expression in the DSL."""
        eval_context = ExpressionContext(
            game_state=game_state,
            current_player_id=context.source_player_id,
            variables=context.variables,
            source_card_id=context.effect.source_card_id if context.effect else None,
        )
        evaluator = ExpressionEvaluator(spec=self.spec)
        return evaluator.evaluate(expr, eval_context)

    def _evaluate_condition(
        self,
        expr: str,
        context: EffectContext,
        game_state: GameState,
    ) -> bool:
        """Evaluate a condition expression."""
        eval_context = ExpressionContext(
            game_state=game_state,
            current_player_id=context.source_player_id,
            variables=context.variables,
            source_card_id=context.effect.source_card_id if context.effect else None,
        )
        evaluator = ExpressionEvaluator(spec=self.spec)
        return evaluator.evaluate_condition(expr, eval_context)

    def _validate_choice(self, chosen_values: list[str]) -> bool:
        """Validate that chosen values are legal."""
        if not self.pending_choice:
            return False

        # Check count constraints
        if len(chosen_values) < self.pending_choice.min_choices:
            return False
        if len(chosen_values) > self.pending_choice.max_choices:
            return False

        # Check values are in options
        for val in chosen_values:
            if val not in self.pending_choice.options:
                return False

        return True


@dataclass
class StepResult:
    """Result of resolving a single step."""
    new_state: GameState | None = None
    needs_choice: bool = False
    pending_choice: PendingChoice | None = None
    sub_context: EffectContext | None = None
    error: str | None = None


# Import Effect here to avoid circular import at module level
from ..spec_schema.effect_dsl import Effect
