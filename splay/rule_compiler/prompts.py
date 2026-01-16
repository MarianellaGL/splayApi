"""
Compiler Prompts - Prompts for LLM-based rule extraction.

These prompts are used at BUILD-TIME to extract game structure
from rules text. They are designed to produce structured output
that can be validated and converted to GameSpec.

STUB: These are placeholder prompts. Full implementation would
include detailed extraction prompts with examples.
"""

from dataclasses import dataclass


@dataclass
class CompilerPrompts:
    """
    Collection of prompts for rule compilation.

    Each prompt targets a specific extraction task.
    Prompts include:
    - System context
    - Extraction instructions
    - Output format specification
    - Examples
    """

    @staticmethod
    def game_overview() -> str:
        """Prompt to extract basic game info."""
        return """
You are a board game rule analyzer. Extract the following from the rules text:

1. Game name
2. Player count (min and max)
3. Game objective / win conditions
4. Core game loop (turn structure)

Output as JSON:
{
    "game_name": "string",
    "min_players": number,
    "max_players": number,
    "win_conditions": ["string"],
    "turn_structure": "string description"
}

Rules text:
{rules_text}
"""

    @staticmethod
    def card_extraction() -> str:
        """Prompt to extract card definitions."""
        return """
You are extracting card information from board game rules.

For each card mentioned, extract:
1. Card name
2. Any numeric values (age, tier, cost, etc.)
3. Card category/type/color
4. Card effects/abilities (as text)
5. Any icons or symbols

Output as JSON array:
[
    {
        "name": "string",
        "values": {"age": number, ...},
        "category": "string",
        "effects": ["effect description"],
        "icons": ["icon name"]
    }
]

Rules text:
{rules_text}
"""

    @staticmethod
    def action_extraction() -> str:
        """Prompt to extract available actions."""
        return """
You are extracting player actions from board game rules.

For each action players can take:
1. Action name
2. When it can be taken (which phase)
3. Requirements/preconditions
4. What it does (effect)
5. Cost if any

Output as JSON array:
[
    {
        "name": "string",
        "phase": "string",
        "preconditions": ["string"],
        "effects": ["string"],
        "cost": "string or null"
    }
]

Rules text:
{rules_text}
"""

    @staticmethod
    def effect_extraction() -> str:
        """Prompt to extract and structure card effects."""
        return """
You are converting card effect text into a structured format.

For the given effect text, break it down into steps:
1. Each atomic action is one step
2. Identify player choices
3. Identify conditional logic (if/then)
4. Identify targeting (self, opponent, all players)
5. Identify loops/repeats

Output as JSON:
{
    "effect_id": "string",
    "trigger": "string or null",
    "steps": [
        {
            "step_type": "draw|meld|score|choose|conditional|...",
            "target": "self|opponent|all",
            "parameters": {},
            "condition": "string or null",
            "then_steps": [],
            "else_steps": []
        }
    ]
}

Effect text:
{effect_text}
"""

    @staticmethod
    def zone_extraction() -> str:
        """Prompt to extract game zones."""
        return """
You are extracting game zones/areas from board game rules.

For each zone where cards or components can exist:
1. Zone name
2. Who owns it (player, shared, none)
3. Visibility (public, private, hidden)
4. Any special properties (stacking, ordering, limits)

Output as JSON array:
[
    {
        "name": "string",
        "owner": "player|shared|none",
        "visibility": "public|private|hidden",
        "properties": {}
    }
]

Rules text:
{rules_text}
"""

    @staticmethod
    def test_generation() -> str:
        """Prompt to generate test cases from rules."""
        return """
You are generating test cases from board game rules.

Based on the rules, generate test scenarios that verify:
1. Legal action validation
2. Effect resolution correctness
3. Win condition checking
4. Edge cases mentioned in rules/FAQ

Output as JSON array of test cases:
[
    {
        "test_name": "string",
        "description": "string",
        "setup": {"game state description"},
        "action": {"action to take"},
        "expected": {"expected result"}
    }
]

Rules text:
{rules_text}
"""

    @staticmethod
    def innovation_specific() -> str:
        """Innovation-specific extraction prompt."""
        return """
You are extracting Innovation card game information.

Innovation-specific elements:
1. Ages (1-10)
2. Colors (red, yellow, green, blue, purple)
3. Icons (castle, crown, leaf, lightbulb, factory, clock)
4. Icon positions (top_left, bottom_left, bottom_center, bottom_right)
5. Splay directions (left, right, up)
6. Effect types (demand, share)

For each card, extract:
{
    "id": "card_name_lowercase",
    "name": "Card Name",
    "age": number,
    "color": "string",
    "icons": {
        "top_left": "icon or empty",
        "bottom_left": "icon or empty",
        "bottom_center": "icon or empty",
        "bottom_right": "icon or empty"
    },
    "dogma": {
        "trigger_icon": "icon name",
        "is_demand": boolean,
        "effect_text": "original text",
        "steps": [structured steps]
    }
}

Card text:
{card_text}
"""
