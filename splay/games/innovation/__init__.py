"""
Innovation - The MVP Game

Innovation is a card game about civilizations progressing through the ages.
Key mechanics:
- Cards have ages (1-10), colors (5), and icons
- Players meld cards to board, building stacks by color
- Splaying reveals icons on cards below
- Dogma effects activate based on icon counts
- First to N achievements wins

This module contains:
- Innovation-specific state model
- Card definitions (subset for MVP)
- Example dogma effects in DSL
- Innovation game spec
"""

from .state import InnovationState, InnovationPlayer
from .spec import create_innovation_spec
from .cards import INNOVATION_CARDS, InnovationCard
from .icons import Icon, count_icons, ICON_POSITIONS

__all__ = [
    "InnovationState",
    "InnovationPlayer",
    "create_innovation_spec",
    "INNOVATION_CARDS",
    "InnovationCard",
    "Icon",
    "count_icons",
    "ICON_POSITIONS",
]
