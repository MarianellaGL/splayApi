"""
Innovation Icons - Icon definitions and counting.

Icons are the core mechanic of Innovation:
- Each card has 4 icon positions (may be empty or have an icon)
- Icon counts determine dogma sharing and demands
- Splay direction affects which icons are visible
"""

from enum import Enum
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...engine_core.state import PlayerState, SplayDirection, ZoneStack
    from ...spec_schema import GameSpec


class Icon(Enum):
    """Innovation icon types."""
    CASTLE = "castle"      # Purple
    CROWN = "crown"        # Yellow
    LEAF = "leaf"          # Green
    LIGHTBULB = "lightbulb"  # Blue
    FACTORY = "factory"    # Red
    CLOCK = "clock"        # Pink/bonus

    # Empty position
    EMPTY = "empty"


# Icon positions on a card:
# [top_left, bottom_left, bottom_center, bottom_right]
#
#  [0]          [empty]
#
#  [1]    [2]     [3]
#
# When splayed left: positions 0, 1 of covered cards visible
# When splayed right: position 3 of covered cards visible
# When splayed up: positions 1, 2, 3 of covered cards visible

ICON_POSITIONS = {
    "top_left": 0,
    "bottom_left": 1,
    "bottom_center": 2,
    "bottom_right": 3,
}


@dataclass
class CardIcons:
    """Icon configuration for a card."""
    top_left: Icon = Icon.EMPTY
    bottom_left: Icon = Icon.EMPTY
    bottom_center: Icon = Icon.EMPTY
    bottom_right: Icon = Icon.EMPTY

    def as_list(self) -> list[Icon]:
        """Return icons as list [top_left, bottom_left, bottom_center, bottom_right]."""
        return [self.top_left, self.bottom_left, self.bottom_center, self.bottom_right]

    def count(self, icon: Icon) -> int:
        """Count occurrences of an icon."""
        return sum(1 for i in self.as_list() if i == icon)


def count_icons(
    player: "PlayerState",
    spec: "GameSpec",
    target_icon: Icon | None = None,
) -> dict[Icon, int] | int:
    """
    Count visible icons for a player.

    If target_icon is specified, returns count for that icon.
    Otherwise returns dict of all icon counts.

    Visibility rules by splay:
    - NONE: Only top card icons visible
    - LEFT: Top card + positions 0,1 of covered cards
    - RIGHT: Top card + position 3 of covered cards
    - UP: Top card + positions 1,2,3 of covered cards
    """
    from ...engine_core.state import SplayDirection

    counts: dict[Icon, int] = {icon: 0 for icon in Icon if icon != Icon.EMPTY}

    for color, stack in player.board.items():
        if stack.is_empty:
            continue

        cards = stack.cards
        splay = stack.splay_direction

        for i, card in enumerate(cards):
            # Get card definition for icons
            card_def = spec.get_card(card.card_id)
            if not card_def:
                continue

            # Parse icons from card definition
            icons = _get_card_icons(card_def)

            is_top = (i == len(cards) - 1)

            if is_top:
                # Top card: all icons visible
                for icon in icons.as_list():
                    if icon != Icon.EMPTY:
                        counts[icon] = counts.get(icon, 0) + 1
            else:
                # Covered card: visibility depends on splay
                visible_positions = _get_visible_positions(splay)
                icon_list = icons.as_list()
                for pos in visible_positions:
                    icon = icon_list[pos]
                    if icon != Icon.EMPTY:
                        counts[icon] = counts.get(icon, 0) + 1

    if target_icon:
        return counts.get(target_icon, 0)

    return counts


def _get_card_icons(card_def) -> CardIcons:
    """Extract CardIcons from card definition."""
    icons_dict = card_def.icons or {}
    return CardIcons(
        top_left=_str_to_icon(icons_dict.get("top_left", "empty")),
        bottom_left=_str_to_icon(icons_dict.get("bottom_left", "empty")),
        bottom_center=_str_to_icon(icons_dict.get("bottom_center", "empty")),
        bottom_right=_str_to_icon(icons_dict.get("bottom_right", "empty")),
    )


def _str_to_icon(s: str) -> Icon:
    """Convert string to Icon enum."""
    try:
        return Icon(s.lower())
    except ValueError:
        return Icon.EMPTY


def _get_visible_positions(splay: "SplayDirection") -> list[int]:
    """Get which positions are visible on covered cards based on splay."""
    from ...engine_core.state import SplayDirection

    if splay == SplayDirection.NONE:
        return []  # Only top card visible
    elif splay == SplayDirection.LEFT:
        return [0, 1]  # Top-left, bottom-left
    elif splay == SplayDirection.RIGHT:
        return [3]  # Bottom-right
    elif splay == SplayDirection.UP:
        return [1, 2, 3]  # All bottom icons
    else:
        return []
