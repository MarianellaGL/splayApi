"""
Bots module - Automa AI implementations.

Provides:
- BotPolicy: Interface for bot decision-making
- HeuristicEvaluator: Scores game states
- InnovationBot: Innovation-specific bot
- Personality: Configurable play styles
"""

from .policy import BotPolicy, BotDecision, RandomPolicy, FirstLegalPolicy
from .evaluator import HeuristicEvaluator, EvaluationWeights
from .personality import Personality, PERSONALITIES
from .innovation_bot import InnovationBot

__all__ = [
    "BotPolicy",
    "BotDecision",
    "RandomPolicy",
    "FirstLegalPolicy",
    "HeuristicEvaluator",
    "EvaluationWeights",
    "Personality",
    "PERSONALITIES",
    "InnovationBot",
]
