"""
Innovation Bot - Automa implementation for Innovation.

This is the MVP bot that:
- Uses 1-ply lookahead
- Applies heuristic evaluation
- Supports configurable personalities
- Generates physical instructions for human

The bot does NOT:
- Use deep search (MCTS, minimax)
- Coordinate with other automas
- Learn from games
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
import random

from .policy import BotPolicy, BotDecision, ChoiceDecision
from .evaluator import HeuristicEvaluator
from .personality import Personality, BALANCED

if TYPE_CHECKING:
    from ..engine_core.state import GameState
    from ..engine_core.action import Action, ActionType
    from ..engine_core.effect_resolver import PendingChoice
    from ..spec_schema import GameSpec


@dataclass
class InnovationBot(BotPolicy):
    """
    Innovation automa with 1-ply heuristic evaluation.

    Usage:
        bot = InnovationBot(player_id="bot1", personality=AGGRESSIVE)
        decision = bot.select_action(state, spec, legal_actions)
        print(decision.physical_instructions)  # What human should do
    """
    player_id: str
    personality: Personality = None  # type: ignore
    evaluator: HeuristicEvaluator = None  # type: ignore
    rng: random.Random = None  # type: ignore

    def __post_init__(self):
        if self.personality is None:
            self.personality = BALANCED
        if self.evaluator is None:
            self.evaluator = HeuristicEvaluator(weights=self.personality.weights)
        if self.rng is None:
            self.rng = random.Random()

    def select_action(
        self,
        state: GameState,
        spec: GameSpec,
        legal_actions: list[Action],
    ) -> BotDecision:
        """
        Select the best action using 1-ply lookahead.

        Process:
        1. Check for random action (personality.randomness)
        2. Evaluate each legal action
        3. Apply personality preferences
        4. Select best (or near-best with some variance)
        5. Generate physical instructions
        """
        if not legal_actions:
            raise ValueError("No legal actions available")

        # Random action check
        if self.rng.random() < self.personality.randomness:
            action = self.rng.choice(legal_actions)
            return self._create_decision(
                action,
                state,
                spec,
                explanation=f"Random action (personality: {self.personality.name})",
                score=0,
                num_evaluated=0,
            )

        # Evaluate all actions
        scored_actions: list[tuple[Action, float]] = []
        for action in legal_actions:
            base_score = self.evaluator.evaluate_action(
                state, spec, action, self.player_id
            )

            # Apply personality preference
            preference = self.personality.action_preferences.get(
                action.action_type.value, 1.0
            )
            adjusted_score = base_score * preference

            scored_actions.append((action, adjusted_score))

        # Sort by score (descending)
        scored_actions.sort(key=lambda x: x[1], reverse=True)

        # Select action (with some variance based on risk tolerance)
        selected_action, best_score = self._select_with_variance(scored_actions)

        return self._create_decision(
            selected_action,
            state,
            spec,
            explanation=self._generate_explanation(selected_action, best_score),
            score=best_score,
            num_evaluated=len(legal_actions),
        )

    def select_choice(
        self,
        state: GameState,
        spec: GameSpec,
        pending_choice: PendingChoice,
    ) -> ChoiceDecision:
        """
        Make a choice during effect resolution.

        Evaluates each option and selects the best.
        """
        if not pending_choice.options:
            # If optional and no options, decline
            if pending_choice.optional:
                return ChoiceDecision(
                    choice_id=pending_choice.choice_id,
                    chosen_values=[],
                    explanation="No options available, declining",
                )
            raise ValueError("No options available for required choice")

        # For card choices, evaluate which cards are best to choose
        if pending_choice.choice_type == "card":
            return self._select_card_choice(state, spec, pending_choice)

        # For player choices, select based on aggression
        if pending_choice.choice_type == "player":
            return self._select_player_choice(state, spec, pending_choice)

        # Default: select first option
        return ChoiceDecision(
            choice_id=pending_choice.choice_id,
            chosen_values=[pending_choice.options[0]],
            explanation="Default selection",
        )

    def _select_card_choice(
        self,
        state: GameState,
        spec: GameSpec,
        choice: PendingChoice,
    ) -> ChoiceDecision:
        """Select cards for a choice."""
        # Score each card option
        scored_cards: list[tuple[str, float]] = []
        for card_id in choice.options:
            card_def = spec.get_card(card_id)
            if not card_def:
                continue

            # Simple heuristic: higher age = better for most choices
            score = float(card_def.age or 0)

            # Adjust based on context
            # STUB: More sophisticated card evaluation
            scored_cards.append((card_id, score))

        scored_cards.sort(key=lambda x: x[1], reverse=True)

        # Select up to max_choices
        num_to_select = min(choice.max_choices, len(scored_cards))
        selected = [card_id for card_id, _ in scored_cards[:num_to_select]]

        return ChoiceDecision(
            choice_id=choice.choice_id,
            chosen_values=selected,
            explanation=f"Selected highest value card(s)",
        )

    def _select_player_choice(
        self,
        state: GameState,
        spec: GameSpec,
        choice: PendingChoice,
    ) -> ChoiceDecision:
        """Select a player target."""
        # Aggressive personalities target the leader
        # Passive personalities target weaker players (to not make enemies)

        player_scores: list[tuple[str, float]] = []
        for player_id in choice.options:
            player = state.get_player(player_id)
            if not player:
                continue

            # Simple score: achievements + score_pile size
            score = (
                player.achievements.count * 10 +
                player.score_pile.count
            )
            player_scores.append((player_id, score))

        player_scores.sort(key=lambda x: x[1], reverse=True)

        # Aggressive: target leader. Passive: target weakest
        if self.personality.aggression > 0.5:
            selected = player_scores[0][0]  # Strongest
        else:
            selected = player_scores[-1][0]  # Weakest

        return ChoiceDecision(
            choice_id=choice.choice_id,
            chosen_values=[selected],
            explanation=f"Selected {'strongest' if self.personality.aggression > 0.5 else 'weakest'} opponent",
        )

    def _select_with_variance(
        self,
        scored_actions: list[tuple[Action, float]],
    ) -> tuple[Action, float]:
        """
        Select from top actions with some variance.

        Higher risk_tolerance = more likely to pick suboptimal action.
        """
        if not scored_actions:
            raise ValueError("No actions to select from")

        if len(scored_actions) == 1:
            return scored_actions[0]

        # Determine how many top actions to consider
        # risk_tolerance 0 = only best, 1 = consider all
        top_n = max(1, int(len(scored_actions) * self.personality.risk_tolerance))
        top_actions = scored_actions[:top_n]

        # Weight by score (softmax-like)
        min_score = min(s for _, s in top_actions)
        weights = [max(0.1, s - min_score + 1) for _, s in top_actions]

        # Random weighted selection
        total = sum(weights)
        r = self.rng.random() * total
        cumulative = 0
        for (action, score), weight in zip(top_actions, weights):
            cumulative += weight
            if r <= cumulative:
                return action, score

        return top_actions[0]  # Fallback

    def _create_decision(
        self,
        action: Action,
        state: GameState,
        spec: GameSpec,
        explanation: str,
        score: float,
        num_evaluated: int,
    ) -> BotDecision:
        """Create a BotDecision with physical instructions."""
        decision = BotDecision(
            action=action,
            explanation=explanation,
            confidence=self._calculate_confidence(score, num_evaluated),
            evaluated_actions=num_evaluated,
            best_score=score,
        )

        # Generate physical instructions for human
        instructions = self._generate_physical_instructions(action, state, spec)
        for instruction in instructions:
            decision.add_instruction(instruction)

        return decision

    def _generate_physical_instructions(
        self,
        action: Action,
        state: GameState,
        spec: GameSpec,
    ) -> list[str]:
        """
        Generate instructions for what human should do on physical table.

        These are clear, unambiguous directions.
        """
        from ..engine_core.action import ActionType

        instructions = []
        player_name = f"Bot ({self.player_id})"

        if action.action_type == ActionType.DRAW:
            age = action.payload.params.get("age", "highest")
            instructions.append(f"{player_name}: Draw the top card from Age {age} deck")
            instructions.append(f"Place it in {player_name}'s hand area")

        elif action.action_type == ActionType.MELD:
            card_id = action.payload.card_id
            card_def = spec.get_card(card_id) if card_id else None
            card_name = card_def.name if card_def else card_id
            color = card_def.color if card_def else "unknown"
            instructions.append(f"{player_name}: Take {card_name} from hand")
            instructions.append(f"Place it on top of the {color} pile")

        elif action.action_type == ActionType.DOGMA:
            card_id = action.payload.card_id
            card_def = spec.get_card(card_id) if card_id else None
            card_name = card_def.name if card_def else card_id
            instructions.append(f"{player_name}: Activate dogma on {card_name}")
            instructions.append("Resolve the effect (see card text)")

        elif action.action_type == ActionType.ACHIEVE:
            achievement_id = action.payload.card_id
            instructions.append(f"{player_name}: Claim the Age {achievement_id} achievement")
            instructions.append("Move achievement card to bot's achievement area")

        elif action.action_type == ActionType.PASS:
            instructions.append(f"{player_name}: Pass (no action)")

        elif action.action_type == ActionType.END_TURN:
            instructions.append(f"{player_name}'s turn is complete")

        return instructions

    def _generate_explanation(self, action: Action, score: float) -> str:
        """Generate explanation for the decision."""
        from ..engine_core.action import ActionType

        action_name = action.action_type.value
        return f"Selected {action_name} (score: {score:.1f}, personality: {self.personality.name})"

    def _calculate_confidence(self, score: float, num_evaluated: int) -> float:
        """Calculate confidence in the decision."""
        if num_evaluated <= 1:
            return 1.0

        # More evaluated actions = more confident in selection
        # Higher score = more confident
        base_confidence = min(1.0, num_evaluated / 10)
        score_boost = min(0.3, score / 100) if score > 0 else 0

        return min(1.0, base_confidence + score_boost)

    def get_name(self) -> str:
        return f"InnovationBot({self.player_id}, {self.personality.name})"


def create_automa_team(
    num_bots: int,
    personalities: list[Personality] | None = None,
    seed: int | None = None,
) -> list[InnovationBot]:
    """
    Create a team of automa bots.

    If personalities not specified, uses BALANCED for all.
    Bots do NOT coordinate - they play independently.
    """
    from .personality import PERSONALITIES, create_random_personality

    if personalities is None:
        # Default to balanced, with some variation
        personalities = []
        personality_names = list(PERSONALITIES.keys())
        rng = random.Random(seed)
        for i in range(num_bots):
            if i < len(personality_names):
                personalities.append(PERSONALITIES[personality_names[i]])
            else:
                personalities.append(create_random_personality(seed=seed))

    bots = []
    for i in range(num_bots):
        personality = personalities[i] if i < len(personalities) else BALANCED
        bot = InnovationBot(
            player_id=f"bot_{i+1}",
            personality=personality,
            rng=random.Random(seed + i if seed else None),
        )
        bots.append(bot)

    return bots
