"""
Bot Policy - Interface for bot decision-making.

A BotPolicy takes a game state and returns a decision.
Decisions include:
- Which action to take
- Responses to choices during effects
- Instructions for the human player to execute
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..engine_core.state import GameState
    from ..engine_core.action import Action
    from ..engine_core.effect_resolver import PendingChoice
    from ..spec_schema import GameSpec


@dataclass
class BotDecision:
    """
    A decision made by a bot.

    Contains:
    - The action to take
    - Explanation (for UI/debugging)
    - Instructions for human (what to physically do)
    - Confidence in the decision
    """
    action: Action
    explanation: str = ""
    confidence: float = 1.0

    # For the human player to execute on physical table
    physical_instructions: list[str] = field(default_factory=list)

    # Evaluation details (for debugging)
    evaluated_actions: int = 0
    best_score: float = 0.0
    evaluation_details: dict[str, Any] = field(default_factory=dict)

    def add_instruction(self, instruction: str):
        """Add a physical instruction."""
        self.physical_instructions.append(instruction)


@dataclass
class ChoiceDecision:
    """
    A decision for a pending choice.

    Used when resolving effects that require player input.
    """
    choice_id: str
    chosen_values: list[str]
    explanation: str = ""


class BotPolicy(ABC):
    """
    Abstract base class for bot policies.

    A policy defines how a bot selects actions.
    Implementations can range from simple heuristics
    to complex search algorithms.
    """

    @abstractmethod
    def select_action(
        self,
        state: GameState,
        spec: GameSpec,
        legal_actions: list[Action],
    ) -> BotDecision:
        """
        Select an action from the legal actions.

        Args:
            state: Current game state
            spec: Game specification
            legal_actions: List of legal actions to choose from

        Returns:
            BotDecision with the selected action
        """
        pass

    @abstractmethod
    def select_choice(
        self,
        state: GameState,
        spec: GameSpec,
        pending_choice: PendingChoice,
    ) -> ChoiceDecision:
        """
        Make a choice when an effect requires input.

        Args:
            state: Current game state
            spec: Game specification
            pending_choice: The choice that needs to be made

        Returns:
            ChoiceDecision with the selected option(s)
        """
        pass

    def get_name(self) -> str:
        """Get the bot's name/identifier."""
        return self.__class__.__name__


class RandomPolicy(BotPolicy):
    """
    Random policy - selects actions uniformly at random.

    Used for:
    - Testing
    - Baseline comparison
    - When no better option available
    """

    def __init__(self, seed: int | None = None):
        import random
        self.rng = random.Random(seed)

    def select_action(
        self,
        state: GameState,
        spec: GameSpec,
        legal_actions: list[Action],
    ) -> BotDecision:
        if not legal_actions:
            raise ValueError("No legal actions available")

        action = self.rng.choice(legal_actions)
        return BotDecision(
            action=action,
            explanation="Selected randomly",
            confidence=1.0 / len(legal_actions),
            evaluated_actions=len(legal_actions),
        )

    def select_choice(
        self,
        state: GameState,
        spec: GameSpec,
        pending_choice: PendingChoice,
    ) -> ChoiceDecision:
        if not pending_choice.options:
            raise ValueError("No options available")

        # Select required number of options randomly
        num_to_select = min(pending_choice.max_choices, len(pending_choice.options))
        selected = self.rng.sample(pending_choice.options, num_to_select)

        return ChoiceDecision(
            choice_id=pending_choice.choice_id,
            chosen_values=selected,
            explanation="Selected randomly",
        )


class FirstLegalPolicy(BotPolicy):
    """
    First-legal policy - always selects the first legal action.

    Used for:
    - Deterministic testing
    - Baseline comparison
    """

    def select_action(
        self,
        state: GameState,
        spec: GameSpec,
        legal_actions: list[Action],
    ) -> BotDecision:
        if not legal_actions:
            raise ValueError("No legal actions available")

        return BotDecision(
            action=legal_actions[0],
            explanation="Selected first legal action",
            evaluated_actions=1,
        )

    def select_choice(
        self,
        state: GameState,
        spec: GameSpec,
        pending_choice: PendingChoice,
    ) -> ChoiceDecision:
        if not pending_choice.options:
            raise ValueError("No options available")

        return ChoiceDecision(
            choice_id=pending_choice.choice_id,
            chosen_values=[pending_choice.options[0]],
            explanation="Selected first option",
        )
