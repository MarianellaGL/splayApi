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

from .state import GameState, PlayerState, Card, Zone, SplayDirection
from .action import ActionResult

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
        """Handle draw step."""
        player_id = self._resolve_target_player(context, step)
        player = game_state.get_player(player_id)
        if not player:
            return StepResult(error=f"Player {player_id} not found")

        count = step.params.get("count", 1)
        age = step.params.get("age")  # May be expression

        if isinstance(age, str):
            age = self._evaluate_expression(age, context, game_state)

        # STUB: Implement actual draw logic
        # For now, return unchanged state
        return StepResult(new_state=game_state)

    def _step_meld(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """Handle meld step."""
        # STUB: Implement meld from choice or specified card
        return StepResult(new_state=game_state)

    def _step_tuck(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """Handle tuck step (add to bottom of pile)."""
        # STUB
        return StepResult(new_state=game_state)

    def _step_return(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """Handle return step (card back to supply)."""
        # STUB
        return StepResult(new_state=game_state)

    def _step_transfer(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """Handle transfer step (card from one zone to another)."""
        # STUB
        return StepResult(new_state=game_state)

    def _step_score(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """Handle score step (move card to score pile)."""
        # STUB
        return StepResult(new_state=game_state)

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
        """Handle for-each loop step."""
        # STUB: Evaluate loop_source, iterate with loop_variable
        return StepResult(new_state=game_state)

    def _step_demand(
        self,
        game_state: GameState,
        context: EffectContext,
        step: EffectStep,
    ) -> StepResult:
        """
        Handle demand step - opponents must execute inner steps.

        In Innovation, demand effects target opponents with fewer
        of the triggering icon.
        """
        # STUB: Set up demand_players_remaining and process
        return StepResult(new_state=game_state)

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
        """Count visible icons for a player."""
        # STUB: Implement icon counting based on splay
        return 0

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
        # STUB: Implement expression evaluation
        # For now, try to parse as int
        try:
            return int(expr)
        except ValueError:
            return context.variables.get(expr, 0)

    def _evaluate_condition(
        self,
        expr: str,
        context: EffectContext,
        game_state: GameState,
    ) -> bool:
        """Evaluate a condition expression."""
        # STUB: Implement condition evaluation
        return True

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
