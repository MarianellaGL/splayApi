"""
Minimal Expression Evaluator for Effect DSL.

Evaluates expressions used in effect steps for conditions, counts, etc.

Supports:
- Literals: integers, strings, booleans
- Property access: player.hand.count, card.age
- Comparisons: ==, !=, <, >, <=, >=
- Boolean operators: and, or, not
- Simple arithmetic: +, -, *, /
- Functions: count(), sum(), has(), max(), min()

Expression syntax is intentionally simple - no full parser needed.
Uses JSON AST format for complex expressions.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING
import re

if TYPE_CHECKING:
    from .state import GameState, PlayerState, Card


@dataclass
class ExpressionContext:
    """
    Context for evaluating expressions.

    Provides access to:
    - Current game state
    - Current player (who is executing)
    - Variables set during effect resolution
    - The card triggering the effect
    """
    game_state: GameState
    current_player_id: str
    variables: dict[str, Any]
    source_card_id: str | None = None

    def get_player(self, player_id: str | None = None) -> PlayerState | None:
        """Get a player by ID, or current player if None."""
        pid = player_id or self.current_player_id
        return self.game_state.get_player(pid)

    def get_variable(self, name: str) -> Any:
        """Get a variable value."""
        return self.variables.get(name)

    def set_variable(self, name: str, value: Any):
        """Set a variable value."""
        self.variables[name] = value


class ExpressionEvaluator:
    """
    Evaluates DSL expressions.

    Expressions can be:
    - Simple values: 3, "red", true
    - Property paths: player.hand.count, card.age
    - Comparisons: player.score >= 10
    - Boolean: has_icon('castle') and age > 2
    - Arithmetic: drawn_card.age + 1
    """

    def __init__(self, spec=None):
        self.spec = spec

    def evaluate(self, expr: str | int | bool | dict, context: ExpressionContext) -> Any:
        """
        Evaluate an expression.

        Args:
            expr: Expression string, literal, or JSON AST
            context: Evaluation context

        Returns:
            Evaluated value
        """
        # Handle literals
        if isinstance(expr, (int, float, bool)):
            return expr

        if isinstance(expr, dict):
            return self._evaluate_ast(expr, context)

        if not isinstance(expr, str):
            return expr

        expr = expr.strip()

        # Try literal parsing
        if expr.isdigit():
            return int(expr)

        if expr.startswith('"') and expr.endswith('"'):
            return expr[1:-1]

        if expr.lower() == "true":
            return True
        if expr.lower() == "false":
            return False

        # Check for comparison operators
        for op in [">=", "<=", "==", "!=", ">", "<"]:
            if op in expr:
                parts = expr.split(op, 1)
                if len(parts) == 2:
                    left = self.evaluate(parts[0].strip(), context)
                    right = self.evaluate(parts[1].strip(), context)
                    return self._compare(left, right, op)

        # Check for boolean operators
        if " and " in expr.lower():
            parts = re.split(r"\s+and\s+", expr, flags=re.IGNORECASE)
            return all(self.evaluate(p.strip(), context) for p in parts)

        if " or " in expr.lower():
            parts = re.split(r"\s+or\s+", expr, flags=re.IGNORECASE)
            return any(self.evaluate(p.strip(), context) for p in parts)

        if expr.lower().startswith("not "):
            return not self.evaluate(expr[4:].strip(), context)

        # Check for arithmetic
        if "+" in expr and not expr.startswith("+"):
            parts = expr.rsplit("+", 1)
            if len(parts) == 2:
                left = self.evaluate(parts[0].strip(), context)
                right = self.evaluate(parts[1].strip(), context)
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left + right

        if "-" in expr and not expr.startswith("-"):
            parts = expr.rsplit("-", 1)
            if len(parts) == 2:
                left = self.evaluate(parts[0].strip(), context)
                right = self.evaluate(parts[1].strip(), context)
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left - right

        # Check for function calls
        func_match = re.match(r"(\w+)\((.*)\)", expr)
        if func_match:
            func_name = func_match.group(1)
            args_str = func_match.group(2)
            return self._call_function(func_name, args_str, context)

        # Property access
        return self._resolve_property(expr, context)

    def evaluate_condition(self, expr: str | dict, context: ExpressionContext) -> bool:
        """Evaluate an expression as a boolean condition."""
        result = self.evaluate(expr, context)
        return bool(result)

    def _compare(self, left: Any, right: Any, op: str) -> bool:
        """Perform comparison operation."""
        try:
            if op == "==":
                return left == right
            elif op == "!=":
                return left != right
            elif op == "<":
                return left < right
            elif op == ">":
                return left > right
            elif op == "<=":
                return left <= right
            elif op == ">=":
                return left >= right
        except TypeError:
            return False
        return False

    def _call_function(self, func_name: str, args_str: str, context: ExpressionContext) -> Any:
        """Call a built-in function."""
        args = [a.strip() for a in args_str.split(",") if a.strip()]

        if func_name == "count":
            # count(zone) - count cards in a zone
            if args:
                zone = self._resolve_property(args[0], context)
                if hasattr(zone, "count"):
                    return zone.count
                if hasattr(zone, "__len__"):
                    return len(zone)
            return 0

        elif func_name == "sum":
            # sum(zone, property) - sum a property over cards in zone
            if len(args) >= 2:
                zone = self._resolve_property(args[0], context)
                prop = args[1].strip("'\"")
                if hasattr(zone, "cards"):
                    total = 0
                    for card in zone.cards:
                        card_def = self.spec.get_card(card.card_id) if self.spec else None
                        if card_def and hasattr(card_def, prop):
                            val = getattr(card_def, prop)
                            if isinstance(val, (int, float)):
                                total += val
                    return total
            return 0

        elif func_name == "has":
            # has(collection, value) - check if collection contains value
            if len(args) >= 2:
                coll = self._resolve_property(args[0], context)
                val = self.evaluate(args[1], context)
                if hasattr(coll, "__contains__"):
                    return val in coll
                if hasattr(coll, "contains"):
                    return coll.contains(val)
            return False

        elif func_name == "has_icon":
            # has_icon(card, icon) - check if card has an icon
            if len(args) >= 1:
                icon = args[0].strip("'\"")
                # Get the card from context
                card_id = context.variables.get("drawn_card") or context.source_card_id
                if card_id and self.spec:
                    card_def = self.spec.get_card(card_id)
                    if card_def and card_def.icons:
                        return icon in card_def.icons.values()
            return False

        elif func_name == "max":
            # max(a, b, ...) or max(collection, property)
            if args:
                values = [self.evaluate(a, context) for a in args]
                numeric = [v for v in values if isinstance(v, (int, float))]
                if numeric:
                    return max(numeric)
            return 0

        elif func_name == "min":
            if args:
                values = [self.evaluate(a, context) for a in args]
                numeric = [v for v in values if isinstance(v, (int, float))]
                if numeric:
                    return min(numeric)
            return 0

        elif func_name == "highest_age":
            # highest_age(player) - get highest top card age
            if args:
                player = self._resolve_property(args[0], context)
                if hasattr(player, "board"):
                    max_age = 0
                    for color, stack in player.board.items():
                        if stack.top_card and self.spec:
                            card_def = self.spec.get_card(stack.top_card.card_id)
                            if card_def and card_def.age and card_def.age > max_age:
                                max_age = card_def.age
                    return max_age
            return 1

        return None

    def _resolve_property(self, path: str, context: ExpressionContext) -> Any:
        """
        Resolve a property path like 'player.hand.count'.
        """
        parts = path.split(".")

        # Start with root object
        root = parts[0]
        obj = None

        if root == "player":
            obj = context.get_player()
        elif root == "current_player":
            obj = context.get_player()
        elif root == "source_player":
            obj = context.get_player(context.current_player_id)
        elif root == "card" or root == "source_card":
            if context.source_card_id and self.spec:
                obj = self.spec.get_card(context.source_card_id)
            else:
                obj = None
        elif root == "drawn_card":
            card_id = context.variables.get("drawn_card")
            if card_id and self.spec:
                obj = self.spec.get_card(card_id)
            else:
                obj = card_id
        elif root == "chosen_card":
            card_id = context.variables.get("chosen_card")
            if card_id and self.spec:
                obj = self.spec.get_card(card_id)
            else:
                obj = card_id
        elif root == "game":
            obj = context.game_state
        elif root in context.variables:
            obj = context.variables[root]
        else:
            # Unknown root - check if it's a special keyword
            if root == "highest_top_card_age":
                return self._call_function("highest_age", "player", context)
            if root == "choice_made":
                return context.variables.get("choice_made", False)
            if root == "second_choice_made":
                return context.variables.get("second_choice_made", False)
            return None

        # Navigate property path
        for part in parts[1:]:
            if obj is None:
                return None

            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                return None

        return obj

    def _evaluate_ast(self, ast: dict, context: ExpressionContext) -> Any:
        """
        Evaluate a JSON AST expression.

        AST format:
        {"op": "compare", "left": ..., "right": ..., "operator": ">="}
        {"op": "and", "operands": [...]}
        {"op": "call", "function": "count", "args": [...]}
        {"op": "property", "path": "player.hand.count"}
        {"op": "literal", "value": 5}
        """
        op = ast.get("op")

        if op == "literal":
            return ast.get("value")

        elif op == "property":
            return self._resolve_property(ast.get("path", ""), context)

        elif op == "compare":
            left = self.evaluate(ast.get("left"), context)
            right = self.evaluate(ast.get("right"), context)
            operator = ast.get("operator", "==")
            return self._compare(left, right, operator)

        elif op == "and":
            operands = ast.get("operands", [])
            return all(self.evaluate(o, context) for o in operands)

        elif op == "or":
            operands = ast.get("operands", [])
            return any(self.evaluate(o, context) for o in operands)

        elif op == "not":
            operand = ast.get("operand")
            return not self.evaluate(operand, context)

        elif op == "call":
            func_name = ast.get("function", "")
            args = ast.get("args", [])
            args_str = ", ".join(str(self.evaluate(a, context)) for a in args)
            return self._call_function(func_name, args_str, context)

        elif op == "add":
            left = self.evaluate(ast.get("left"), context)
            right = self.evaluate(ast.get("right"), context)
            return (left or 0) + (right or 0)

        elif op == "subtract":
            left = self.evaluate(ast.get("left"), context)
            right = self.evaluate(ast.get("right"), context)
            return (left or 0) - (right or 0)

        return None


# Convenience function
def evaluate_expression(
    expr: str | int | bool | dict,
    game_state: GameState,
    player_id: str,
    variables: dict | None = None,
    spec=None,
) -> Any:
    """
    Evaluate an expression in a game context.

    Args:
        expr: Expression to evaluate
        game_state: Current game state
        player_id: ID of current player
        variables: Optional variables dict
        spec: Optional GameSpec for card lookups

    Returns:
        Evaluated value
    """
    context = ExpressionContext(
        game_state=game_state,
        current_player_id=player_id,
        variables=variables or {},
    )
    evaluator = ExpressionEvaluator(spec=spec)
    return evaluator.evaluate(expr, context)
