"""
Innovation Cards - Card definitions for MVP.

This module contains a subset of Innovation cards for testing.
Full card set would be compiled from rules text.

Card structure:
- Age (1-10)
- Color (red, yellow, green, blue, purple)
- Icons (4 positions: top_left, bottom_left, bottom_center, bottom_right)
- Effects (dogma effects)
"""

from dataclasses import dataclass, field
from typing import Any

from ...spec_schema.game_spec import CardDefinition
from ...spec_schema.effect_dsl import (
    Effect,
    EffectStep,
    StepType,
    TargetSelector,
    TargetType,
    Condition,
    ChoiceSpec,
    draw_step,
    meld_step,
    choose_card_step,
    conditional_step,
    splay_step,
    demand_step,
)
from .icons import Icon


@dataclass
class InnovationCard:
    """
    Innovation card with full definition.

    This is a convenience class for defining cards.
    Gets converted to CardDefinition for the spec.
    """
    id: str
    name: str
    age: int
    color: str

    # Icons as dict: position -> icon
    icons: dict[str, str] = field(default_factory=dict)

    # Dogma effects
    dogma_effects: list[Effect] = field(default_factory=list)

    # Keywords (e.g., "demand", "share")
    keywords: list[str] = field(default_factory=list)

    def to_card_definition(self) -> CardDefinition:
        """Convert to generic CardDefinition."""
        return CardDefinition(
            id=self.id,
            name=self.name,
            age=self.age,
            color=self.color,
            icons=self.icons,
            effects=self.dogma_effects,
            keywords=self.keywords,
        )


# ============================================================================
# Example Age 1 Cards
# ============================================================================

ARCHERY = InnovationCard(
    id="archery",
    name="Archery",
    age=1,
    color="red",
    icons={
        "top_left": "castle",
        "bottom_left": "lightbulb",
        "bottom_center": "empty",
        "bottom_right": "castle",
    },
    keywords=["demand"],
    dogma_effects=[
        Effect(
            effect_id="archery_dogma",
            name="Archery Dogma",
            effect_type="dogma",
            trigger_icon="castle",
            description="I demand you draw a 1, then transfer the highest card from your hand to my hand!",
            steps=[
                # Demand: opponent draws, then transfers highest
                EffectStep(
                    step_type=StepType.DEMAND,
                    step_id="archery_demand",
                    target=TargetSelector(target_type=TargetType.ALL_OPPONENTS),
                    loop_steps=[
                        draw_step("demand_draw", count=1, age="1"),
                        # Choose highest card in hand
                        EffectStep(
                            step_type=StepType.TRANSFER,
                            step_id="demand_transfer",
                            params={
                                "source": "hand",
                                "destination": "opponent_hand",  # Demanding player
                                "selection": "highest_age",
                            },
                        ),
                    ],
                ),
            ],
        ),
    ],
)


METALWORKING = InnovationCard(
    id="metalworking",
    name="Metalworking",
    age=1,
    color="red",
    icons={
        "top_left": "castle",
        "bottom_left": "castle",
        "bottom_center": "empty",
        "bottom_right": "castle",
    },
    keywords=["repeat"],
    dogma_effects=[
        Effect(
            effect_id="metalworking_dogma",
            name="Metalworking Dogma",
            effect_type="dogma",
            trigger_icon="castle",
            description="Draw and reveal a 1. If it has a castle, score it and repeat.",
            steps=[
                EffectStep(
                    step_type=StepType.REPEAT,
                    step_id="metalworking_loop",
                    max_iterations=105,  # Safety bound (deck size)
                    loop_steps=[
                        # Draw and reveal
                        EffectStep(
                            step_type=StepType.DRAW,
                            step_id="draw_reveal",
                            params={"count": 1, "age": "1", "reveal": True},
                            target=TargetSelector(target_type=TargetType.SELF),
                        ),
                        # Check for castle
                        conditional_step(
                            step_id="check_castle",
                            condition_expr="drawn_card.has_icon('castle')",
                            then_steps=[
                                EffectStep(
                                    step_type=StepType.SCORE,
                                    step_id="score_drawn",
                                    params={"card": "drawn_card"},
                                ),
                                # Continue loop (implicit)
                            ],
                            else_steps=[
                                # Keep in hand, stop loop
                                EffectStep(
                                    step_type=StepType.SET_VARIABLE,
                                    step_id="stop_loop",
                                    params={"variable": "_break", "value": True},
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ],
)


WRITING = InnovationCard(
    id="writing",
    name="Writing",
    age=1,
    color="blue",
    icons={
        "top_left": "empty",
        "bottom_left": "lightbulb",
        "bottom_center": "lightbulb",
        "bottom_right": "crown",
    },
    dogma_effects=[
        Effect(
            effect_id="writing_dogma",
            name="Writing Dogma",
            effect_type="dogma",
            trigger_icon="lightbulb",
            description="Draw a 2.",
            steps=[
                draw_step("writing_draw", count=1, age="2"),
            ],
        ),
    ],
)


THE_WHEEL = InnovationCard(
    id="the_wheel",
    name="The Wheel",
    age=1,
    color="green",
    icons={
        "top_left": "empty",
        "bottom_left": "castle",
        "bottom_center": "castle",
        "bottom_right": "empty",
    },
    dogma_effects=[
        Effect(
            effect_id="the_wheel_dogma",
            name="The Wheel Dogma",
            effect_type="dogma",
            trigger_icon="castle",
            description="Draw two 1s.",
            steps=[
                draw_step("wheel_draw", count=2, age="1"),
            ],
        ),
    ],
)


AGRICULTURE = InnovationCard(
    id="agriculture",
    name="Agriculture",
    age=1,
    color="yellow",
    icons={
        "top_left": "empty",
        "bottom_left": "leaf",
        "bottom_center": "leaf",
        "bottom_right": "leaf",
    },
    dogma_effects=[
        Effect(
            effect_id="agriculture_dogma",
            name="Agriculture Dogma",
            effect_type="dogma",
            trigger_icon="leaf",
            description="You may return a card from your hand. If you do, draw and score a card of value one higher.",
            steps=[
                choose_card_step(
                    step_id="choose_return",
                    source="hand",
                    optional=True,
                    prompt="Choose a card to return (optional)",
                ),
                conditional_step(
                    step_id="if_returned",
                    condition_expr="choice_made",
                    then_steps=[
                        EffectStep(
                            step_type=StepType.RETURN,
                            step_id="return_chosen",
                            params={"card": "chosen_card"},
                        ),
                        EffectStep(
                            step_type=StepType.DRAW,
                            step_id="draw_higher",
                            params={"age": "returned_card.age + 1"},
                        ),
                        EffectStep(
                            step_type=StepType.SCORE,
                            step_id="score_drawn",
                            params={"card": "drawn_card"},
                        ),
                    ],
                ),
            ],
        ),
    ],
)


# ============================================================================
# Example Age 2 Card
# ============================================================================

CALENDAR = InnovationCard(
    id="calendar",
    name="Calendar",
    age=2,
    color="blue",
    icons={
        "top_left": "empty",
        "bottom_left": "leaf",
        "bottom_center": "leaf",
        "bottom_right": "lightbulb",
    },
    dogma_effects=[
        Effect(
            effect_id="calendar_dogma",
            name="Calendar Dogma",
            effect_type="dogma",
            trigger_icon="leaf",
            description="If you have more cards in your score pile than in your hand, draw two 3s.",
            steps=[
                conditional_step(
                    step_id="check_score_hand",
                    condition_expr="player.score_pile.count > player.hand.count",
                    then_steps=[
                        draw_step("calendar_draw", count=2, age="3"),
                    ],
                ),
            ],
        ),
    ],
)


ROAD_BUILDING = InnovationCard(
    id="road_building",
    name="Road Building",
    age=2,
    color="red",
    icons={
        "top_left": "castle",
        "bottom_left": "castle",
        "bottom_center": "empty",
        "bottom_right": "castle",
    },
    dogma_effects=[
        Effect(
            effect_id="road_building_dogma",
            name="Road Building Dogma",
            effect_type="dogma",
            trigger_icon="castle",
            description="Meld one or two cards from your hand. If you melded two, transfer your top red or yellow card to another player's board.",
            steps=[
                choose_card_step(
                    step_id="choose_meld_1",
                    source="hand",
                    prompt="Choose a card to meld",
                ),
                meld_step("meld_first", card_source="chosen_card"),
                choose_card_step(
                    step_id="choose_meld_2",
                    source="hand",
                    optional=True,
                    prompt="Choose another card to meld (optional)",
                ),
                conditional_step(
                    step_id="if_melded_two",
                    condition_expr="second_choice_made",
                    then_steps=[
                        meld_step("meld_second", card_source="chosen_card_2"),
                        # Transfer top red or yellow
                        EffectStep(
                            step_type=StepType.CHOOSE_OPTION,
                            step_id="choose_color",
                            choice_spec=ChoiceSpec(
                                choice_type="option",
                                source="[red, yellow]",
                                prompt="Choose red or yellow to transfer",
                            ),
                        ),
                        EffectStep(
                            step_type=StepType.CHOOSE_PLAYER,
                            step_id="choose_recipient",
                            choice_spec=ChoiceSpec(
                                choice_type="player",
                                source="other_players",
                                prompt="Choose a player to receive the card",
                            ),
                        ),
                        EffectStep(
                            step_type=StepType.TRANSFER,
                            step_id="transfer_card",
                            params={
                                "source": "board",
                                "color": "chosen_color",
                                "destination": "target_player.board",
                            },
                        ),
                    ],
                ),
            ],
        ),
    ],
)


# ============================================================================
# Card Collection
# ============================================================================

INNOVATION_CARDS: list[InnovationCard] = [
    # Age 1
    ARCHERY,
    METALWORKING,
    WRITING,
    THE_WHEEL,
    AGRICULTURE,
    # Age 2
    CALENDAR,
    ROAD_BUILDING,
]


def get_all_card_definitions() -> list[CardDefinition]:
    """Get all cards as CardDefinitions for the spec."""
    return [card.to_card_definition() for card in INNOVATION_CARDS]


def get_card_by_id(card_id: str) -> InnovationCard | None:
    """Look up a card by ID."""
    for card in INNOVATION_CARDS:
        if card.id == card_id:
            return card
    return None
