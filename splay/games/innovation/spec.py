"""
Innovation Game Specification

This is the MVP game spec for Innovation.
Hand-authored for now; future versions will be LLM-compiled from rules.

The spec defines:
- Resources (icons)
- Zones (hand, board, score pile, achievements, decks)
- Actions (draw, meld, dogma, achieve)
- Turn structure
- Win conditions
"""

from ...spec_schema.game_spec import (
    GameSpec,
    ResourceDefinition,
    ZoneDefinition,
    ActionDefinition,
    PhaseDefinition,
    PhaseType,
    TurnStructure,
    WinCondition,
    WinConditionType,
)
from ...spec_schema.effect_dsl import (
    Effect,
    EffectStep,
    StepType,
    TargetSelector,
    TargetType,
    draw_step,
)
from .cards import get_all_card_definitions


def create_innovation_spec() -> GameSpec:
    """
    Create the Innovation game specification.

    This is the complete definition of Innovation rules
    in a machine-readable format.
    """
    return GameSpec(
        game_id="innovation_base",
        game_name="Innovation (Base Game)",
        version="1.0.0",
        min_players=2,
        max_players=4,
        resources=_define_resources(),
        zones=_define_zones(),
        cards=get_all_card_definitions(),
        actions=_define_actions(),
        turn_structure=_define_turn_structure(),
        win_conditions=_define_win_conditions(),
        setup_effects=_define_setup(),
        metadata={
            "publisher": "Asmadi Games",
            "designer": "Carl Chudyk",
            "year": 2010,
            "bgg_id": 63888,
        },
    )


def _define_resources() -> list[ResourceDefinition]:
    """Define the icons/resources in Innovation."""
    return [
        ResourceDefinition(name="castle", icon="🏰", description="Military/construction"),
        ResourceDefinition(name="crown", icon="👑", description="Political power"),
        ResourceDefinition(name="leaf", icon="🌿", description="Agriculture/nature"),
        ResourceDefinition(name="lightbulb", icon="💡", description="Ideas/innovation"),
        ResourceDefinition(name="factory", icon="🏭", description="Industry/production"),
        ResourceDefinition(name="clock", icon="🕐", description="Time/bonus"),
    ]


def _define_zones() -> list[ZoneDefinition]:
    """Define all zones in the game."""
    zones = []

    # Player zones
    zones.append(ZoneDefinition(
        name="hand",
        owner="player",
        visibility="private",
        ordered=False,
    ))
    zones.append(ZoneDefinition(
        name="score_pile",
        owner="player",
        visibility="hidden",  # Cards visible, but only count matters usually
        ordered=False,
    ))
    zones.append(ZoneDefinition(
        name="achievements",
        owner="player",
        visibility="public",
        ordered=False,
    ))

    # Board stacks (one per color)
    for color in ["red", "yellow", "green", "blue", "purple"]:
        zones.append(ZoneDefinition(
            name=f"board_{color}",
            owner="player",
            visibility="public",
            ordered=True,
            layout="stack",  # Cards stack, can be splayed
        ))

    # Shared zones - age decks
    for age in range(1, 11):
        zones.append(ZoneDefinition(
            name=f"age_{age}",
            owner="shared",
            visibility="hidden",
            ordered=True,
        ))

    # Achievement supply
    zones.append(ZoneDefinition(
        name="achievements_supply",
        owner="shared",
        visibility="public",
    ))
    zones.append(ZoneDefinition(
        name="special_achievements",
        owner="shared",
        visibility="public",
    ))

    return zones


def _define_actions() -> list[ActionDefinition]:
    """Define available player actions."""
    return [
        ActionDefinition(
            name="draw",
            description="Draw a card from the supply",
            phases=["action"],
            effects=[
                Effect(
                    effect_id="draw_effect",
                    name="Draw Card",
                    steps=[
                        EffectStep(
                            step_type=StepType.DRAW,
                            step_id="draw_card",
                            target=TargetSelector(target_type=TargetType.SELF),
                            params={"age": "highest_top_card_age"},
                        ),
                    ],
                ),
            ],
        ),
        ActionDefinition(
            name="meld",
            description="Play a card from your hand to your board",
            phases=["action"],
            parameters={"card_id": "string"},
            preconditions=["player.hand.count > 0"],
            effects=[
                Effect(
                    effect_id="meld_effect",
                    name="Meld Card",
                    steps=[
                        EffectStep(
                            step_type=StepType.MELD,
                            step_id="meld_card",
                            target=TargetSelector(target_type=TargetType.SELF),
                            params={"card": "action.card_id"},
                        ),
                    ],
                ),
            ],
        ),
        ActionDefinition(
            name="dogma",
            description="Execute the dogma effect of a top card",
            phases=["action"],
            parameters={"card_id": "string"},
            preconditions=["card.is_top_of_stack"],
            effects=[
                Effect(
                    effect_id="dogma_effect",
                    name="Execute Dogma",
                    effect_type="dogma",
                    steps=[
                        EffectStep(
                            step_type=StepType.EXECUTE_EFFECT,
                            step_id="run_dogma",
                            params={"effect": "card.dogma_effects"},
                        ),
                    ],
                ),
            ],
        ),
        ActionDefinition(
            name="achieve",
            description="Claim an available achievement",
            phases=["action"],
            parameters={"achievement_id": "string"},
            preconditions=[
                "player.score >= achievement.age * 5",
                "player.highest_top_card_age >= achievement.age",
            ],
            effects=[
                Effect(
                    effect_id="achieve_effect",
                    name="Claim Achievement",
                    steps=[
                        EffectStep(
                            step_type=StepType.ACHIEVE,
                            step_id="claim",
                            params={"achievement": "action.achievement_id"},
                        ),
                    ],
                ),
            ],
        ),
    ]


def _define_turn_structure() -> TurnStructure:
    """Define how turns work."""
    return TurnStructure(
        phases=[
            PhaseDefinition(
                name="action",
                phase_type=PhaseType.ACTION,
                actions_allowed=2,  # 2 actions per turn (1 on first turn)
                optional_actions=["draw", "meld", "dogma", "achieve"],
            ),
        ],
        actions_per_turn=2,
        can_pass=True,
        turn_order="clockwise",
    )


def _define_win_conditions() -> list[WinCondition]:
    """Define how to win."""
    return [
        WinCondition(
            condition_type=WinConditionType.ACHIEVEMENT_COUNT,
            threshold=6,  # For 2 players; adjusted at runtime
            description="Claim the required number of achievements",
        ),
        WinCondition(
            condition_type=WinConditionType.DECK_EXHAUSTION,
            description="If a player would draw from an empty age 10 deck, highest score wins",
            check_expression="all_decks_exhausted and draw_required",
        ),
    ]


def _define_setup() -> list[Effect]:
    """Define game setup steps."""
    return [
        Effect(
            effect_id="setup_deal",
            name="Deal Initial Cards",
            steps=[
                # Each player draws 2 age-1 cards
                EffectStep(
                    step_type=StepType.FOR_EACH,
                    step_id="deal_hands",
                    loop_variable="player",
                    loop_source="all_players",
                    loop_steps=[
                        draw_step("initial_draw", count=2, age="1"),
                    ],
                ),
            ],
        ),
        Effect(
            effect_id="setup_meld",
            name="Initial Meld",
            description="Each player melds one card from hand",
            steps=[
                EffectStep(
                    step_type=StepType.FOR_EACH,
                    step_id="initial_melds",
                    loop_variable="player",
                    loop_source="all_players",
                    loop_steps=[
                        EffectStep(
                            step_type=StepType.CHOOSE_CARD,
                            step_id="choose_meld",
                            choice_spec=None,  # STUB
                        ),
                        EffectStep(
                            step_type=StepType.MELD,
                            step_id="meld_initial",
                            params={"card": "chosen_card"},
                        ),
                    ],
                ),
            ],
        ),
    ]
