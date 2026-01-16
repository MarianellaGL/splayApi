"""
Heuristic Evaluator - Scores game states for bot decision-making.

The evaluator assigns a numeric score to game states based on:
- Position features (score, achievements, board state)
- Opportunity features (available actions)
- Threat features (opponent progress)

Weights can be adjusted to create different personalities.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..engine_core.state import GameState, PlayerState
    from ..spec_schema import GameSpec


@dataclass
class EvaluationWeights:
    """
    Weights for the heuristic evaluator.

    Higher values = more importance.
    Can be adjusted to create different play styles.
    """
    # Score-related
    score_per_point: float = 1.0
    score_pile_count: float = 0.5

    # Achievement-related
    achievement_value: float = 50.0
    close_to_achievement: float = 10.0  # When nearly able to achieve

    # Board-related
    top_card_age: float = 3.0
    board_coverage: float = 2.0  # Having cards in all colors
    splay_value: float = 5.0  # Per splay direction

    # Icon-related
    icon_count: float = 0.5  # Per visible icon
    icon_majority: float = 5.0  # Having more of an icon than opponents

    # Hand-related
    hand_size: float = 1.0
    hand_quality: float = 0.5  # Average age of cards in hand

    # Opponent-related
    opponent_penalty: float = -0.3  # Multiply opponent's score by this

    # Action opportunity
    dogma_available: float = 2.0  # Per dogma action available
    achieve_available: float = 15.0  # If can achieve now


@dataclass
class StateEvaluation:
    """
    Result of evaluating a game state.
    """
    total_score: float
    player_scores: dict[str, float] = field(default_factory=dict)
    feature_breakdown: dict[str, float] = field(default_factory=dict)


class HeuristicEvaluator:
    """
    Evaluates game states using weighted heuristics.

    Used by bots for 1-ply lookahead:
    1. Generate legal actions
    2. Apply each action to get new state
    3. Evaluate new states
    4. Select action leading to best state
    """

    def __init__(self, weights: EvaluationWeights | None = None):
        self.weights = weights or EvaluationWeights()

    def evaluate(
        self,
        state: GameState,
        spec: GameSpec,
        for_player_id: str,
    ) -> StateEvaluation:
        """
        Evaluate a game state from a player's perspective.

        Returns positive score if state is good for player,
        negative if bad.
        """
        features: dict[str, float] = {}
        player_scores: dict[str, float] = {}

        # Evaluate each player
        for player in state.players:
            player_score = self._evaluate_player(player, state, spec)
            player_scores[player.player_id] = player_score

        # Calculate relative score for the evaluating player
        my_score = player_scores.get(for_player_id, 0)
        opponent_scores = [s for pid, s in player_scores.items() if pid != for_player_id]

        if opponent_scores:
            avg_opponent = sum(opponent_scores) / len(opponent_scores)
            relative_score = my_score + (self.weights.opponent_penalty * avg_opponent)
        else:
            relative_score = my_score

        features["relative_score"] = relative_score

        # Check for winning state
        winner = self._check_winner(state, spec)
        if winner == for_player_id:
            relative_score += 1000  # Winning is very good
        elif winner:
            relative_score -= 1000  # Losing is very bad

        return StateEvaluation(
            total_score=relative_score,
            player_scores=player_scores,
            feature_breakdown=features,
        )

    def evaluate_action(
        self,
        state: GameState,
        spec: GameSpec,
        action,
        for_player_id: str,
    ) -> float:
        """
        Evaluate an action by applying it and evaluating resulting state.

        This is the core of 1-ply lookahead.
        """
        from ..engine_core.reducer import apply_action

        result = apply_action(spec, state, action)
        if not result.success or not result.new_state:
            return float("-inf")  # Invalid action

        evaluation = self.evaluate(result.new_state, spec, for_player_id)
        return evaluation.total_score

    def _evaluate_player(
        self,
        player: PlayerState,
        state: GameState,
        spec: GameSpec,
    ) -> float:
        """Evaluate a single player's position."""
        score = 0.0

        # Score pile value
        score_pile_value = self._calculate_score_pile(player, spec)
        score += score_pile_value * self.weights.score_per_point
        score += player.score_pile.count * self.weights.score_pile_count

        # Achievements
        score += player.achievements.count * self.weights.achievement_value

        # Check if close to achieving
        score += self._evaluate_achievement_proximity(player, state, spec)

        # Board evaluation
        score += self._evaluate_board(player, state, spec)

        # Hand evaluation
        score += self._evaluate_hand(player, spec)

        return score

    def _calculate_score_pile(self, player: PlayerState, spec: GameSpec) -> int:
        """Calculate total score from score pile."""
        total = 0
        for card in player.score_pile.cards:
            card_def = spec.get_card(card.card_id)
            if card_def and card_def.age:
                total += card_def.age
        return total

    def _evaluate_achievement_proximity(
        self,
        player: PlayerState,
        state: GameState,
        spec: GameSpec,
    ) -> float:
        """Evaluate how close player is to achievements."""
        score = 0.0
        player_score = self._calculate_score_pile(player, spec)
        highest_age = self._get_highest_top_card_age(player, spec)

        for card in state.achievements.cards:
            card_def = spec.get_card(card.card_id)
            if not card_def or card_def.age is None:
                continue

            required_score = card_def.age * 5
            required_age = card_def.age

            # Can achieve now
            if player_score >= required_score and highest_age >= required_age:
                score += self.weights.achieve_available

            # Close to achieving (within 5 points)
            elif player_score >= required_score - 5 and highest_age >= required_age:
                score += self.weights.close_to_achievement * 0.5

            # Have age but need score
            elif highest_age >= required_age and player_score >= required_score * 0.7:
                score += self.weights.close_to_achievement * 0.3

        return score

    def _evaluate_board(
        self,
        player: PlayerState,
        state: GameState,
        spec: GameSpec,
    ) -> float:
        """Evaluate board state."""
        score = 0.0

        colors_with_cards = 0
        total_top_age = 0
        total_splay_value = 0

        for color, stack in player.board.items():
            if stack.is_empty:
                continue

            colors_with_cards += 1

            # Top card age
            if stack.top_card:
                card_def = spec.get_card(stack.top_card.card_id)
                if card_def and card_def.age:
                    total_top_age += card_def.age

            # Splay value
            from ..engine_core.state import SplayDirection
            if stack.splay_direction != SplayDirection.NONE:
                # Up splay is most valuable, then right, then left
                splay_multiplier = {
                    SplayDirection.UP: 2.0,
                    SplayDirection.RIGHT: 1.5,
                    SplayDirection.LEFT: 1.0,
                }.get(stack.splay_direction, 0)
                total_splay_value += splay_multiplier * len(stack.cards)

        score += total_top_age * self.weights.top_card_age
        score += colors_with_cards * self.weights.board_coverage
        score += total_splay_value * self.weights.splay_value

        return score

    def _evaluate_hand(self, player: PlayerState, spec: GameSpec) -> float:
        """Evaluate hand quality."""
        score = 0.0

        score += player.hand.count * self.weights.hand_size

        # Average age of cards in hand
        if player.hand.count > 0:
            total_age = 0
            for card in player.hand.cards:
                card_def = spec.get_card(card.card_id)
                if card_def and card_def.age:
                    total_age += card_def.age
            avg_age = total_age / player.hand.count
            score += avg_age * self.weights.hand_quality

        return score

    def _get_highest_top_card_age(self, player: PlayerState, spec: GameSpec) -> int:
        """Get highest age among top cards."""
        max_age = 0
        for stack in player.board.values():
            if stack.top_card:
                card_def = spec.get_card(stack.top_card.card_id)
                if card_def and card_def.age and card_def.age > max_age:
                    max_age = card_def.age
        return max_age

    def _check_winner(self, state: GameState, spec: GameSpec) -> str | None:
        """Check if there's a winner."""
        # Achievement win
        target_achievements = {2: 6, 3: 5, 4: 4}.get(state.num_players, 6)
        for player in state.players:
            if player.achievements.count >= target_achievements:
                return player.player_id

        return None
