"""
Bot Personalities - Configurable play styles.

Personalities adjust:
- Evaluation weights (what the bot values)
- Risk tolerance (how much variance is acceptable)
- Aggression (target opponents vs build own position)
- Randomness (for unpredictability)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from .evaluator import EvaluationWeights


@dataclass
class Personality:
    """
    A bot personality that defines play style.

    Personalities can be:
    - Predefined (aggressive, defensive, balanced)
    - Generated (random variations)
    - Tuned (via machine learning)
    """
    name: str
    description: str = ""

    # Evaluation weights
    weights: EvaluationWeights = field(default_factory=EvaluationWeights)

    # Behavioral parameters
    risk_tolerance: float = 0.5  # 0 = avoid risk, 1 = embrace risk
    aggression: float = 0.5  # 0 = passive, 1 = aggressive
    randomness: float = 0.1  # Probability of random action

    # Action preferences (multipliers)
    action_preferences: dict[str, float] = field(default_factory=dict)

    # Dogma preferences by icon
    icon_preferences: dict[str, float] = field(default_factory=dict)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Predefined Personalities
# ============================================================================

BALANCED = Personality(
    name="Balanced",
    description="Well-rounded play style, adapts to situation",
    weights=EvaluationWeights(),
    risk_tolerance=0.5,
    aggression=0.5,
    randomness=0.1,
    action_preferences={
        "draw": 1.0,
        "meld": 1.0,
        "dogma": 1.0,
        "achieve": 1.5,  # Slightly prefer achieving
    },
)


AGGRESSIVE = Personality(
    name="Aggressive",
    description="Focuses on attacking opponents via demand effects",
    weights=EvaluationWeights(
        opponent_penalty=-0.5,  # More weight on hurting opponents
        dogma_available=4.0,  # Values dogma highly
        icon_majority=8.0,  # Wants icon majorities for demands
    ),
    risk_tolerance=0.7,
    aggression=0.8,
    randomness=0.05,
    action_preferences={
        "draw": 0.8,
        "meld": 0.9,
        "dogma": 1.5,  # Prefer dogma
        "achieve": 1.2,
    },
    icon_preferences={
        "castle": 1.3,  # Castle is often for demands
    },
)


BUILDER = Personality(
    name="Builder",
    description="Focuses on building board and scoring, avoids conflict",
    weights=EvaluationWeights(
        score_per_point=1.5,
        board_coverage=4.0,
        splay_value=8.0,
        opponent_penalty=-0.1,  # Less concerned with opponents
        hand_size=2.0,
    ),
    risk_tolerance=0.3,
    aggression=0.2,
    randomness=0.1,
    action_preferences={
        "draw": 1.2,
        "meld": 1.3,  # Prefer melding
        "dogma": 0.7,  # Less dogma
        "achieve": 1.4,
    },
)


RUSHER = Personality(
    name="Rusher",
    description="Tries to win quickly via achievements",
    weights=EvaluationWeights(
        achievement_value=80.0,  # Very high achievement value
        close_to_achievement=20.0,
        achieve_available=30.0,
        score_per_point=2.0,  # Score matters for achievements
        top_card_age=5.0,  # Higher ages enable achievements
    ),
    risk_tolerance=0.6,
    aggression=0.4,
    randomness=0.05,
    action_preferences={
        "draw": 0.9,
        "meld": 1.0,
        "dogma": 0.8,  # Dogma only if it helps scoring
        "achieve": 2.0,  # Strongly prefer achieve
    },
)


CHAOTIC = Personality(
    name="Chaotic",
    description="Unpredictable play with high randomness",
    weights=EvaluationWeights(),
    risk_tolerance=0.9,
    aggression=0.5,
    randomness=0.4,  # 40% chance of random action
    action_preferences={
        "draw": 1.0,
        "meld": 1.0,
        "dogma": 1.2,  # Slightly prefer dogma for chaos
        "achieve": 1.0,
    },
)


# All predefined personalities
PERSONALITIES: dict[str, Personality] = {
    "balanced": BALANCED,
    "aggressive": AGGRESSIVE,
    "builder": BUILDER,
    "rusher": RUSHER,
    "chaotic": CHAOTIC,
}


def create_random_personality(
    name: str = "Random",
    base: Personality | None = None,
    variance: float = 0.3,
    seed: int | None = None,
) -> Personality:
    """
    Create a personality with random variations.

    Args:
        name: Name for the personality
        base: Base personality to vary from (default: BALANCED)
        variance: How much to vary (0-1)
        seed: Random seed for reproducibility
    """
    import random
    rng = random.Random(seed)

    base = base or BALANCED

    def vary(value: float) -> float:
        """Apply random variation to a value."""
        delta = value * variance * (rng.random() * 2 - 1)
        return max(0, value + delta)

    # Vary weights
    new_weights = EvaluationWeights(
        score_per_point=vary(base.weights.score_per_point),
        score_pile_count=vary(base.weights.score_pile_count),
        achievement_value=vary(base.weights.achievement_value),
        close_to_achievement=vary(base.weights.close_to_achievement),
        top_card_age=vary(base.weights.top_card_age),
        board_coverage=vary(base.weights.board_coverage),
        splay_value=vary(base.weights.splay_value),
        icon_count=vary(base.weights.icon_count),
        icon_majority=vary(base.weights.icon_majority),
        hand_size=vary(base.weights.hand_size),
        hand_quality=vary(base.weights.hand_quality),
        opponent_penalty=base.weights.opponent_penalty * (1 + variance * (rng.random() * 2 - 1)),
        dogma_available=vary(base.weights.dogma_available),
        achieve_available=vary(base.weights.achieve_available),
    )

    return Personality(
        name=name,
        description=f"Randomly varied from {base.name}",
        weights=new_weights,
        risk_tolerance=max(0, min(1, base.risk_tolerance + variance * (rng.random() * 2 - 1))),
        aggression=max(0, min(1, base.aggression + variance * (rng.random() * 2 - 1))),
        randomness=max(0, min(1, base.randomness + variance * 0.5 * (rng.random() * 2 - 1))),
        action_preferences=base.action_preferences.copy(),
        metadata={"base": base.name, "variance": variance, "seed": seed},
    )
