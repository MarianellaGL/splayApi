"""
Splay CLI - Command-line interface for the engine.

Usage:
    splay compile <rules_file>     Compile rules to GameSpec
    splay play <spec_file>         Start a game session
    splay validate <spec_file>     Validate a GameSpec

STUB: Minimal implementation for testing.
"""

import argparse
import sys


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Splay - Board Game Automa Engine",
        prog="splay",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Compile command
    compile_parser = subparsers.add_parser("compile", help="Compile rules to GameSpec")
    compile_parser.add_argument("rules_file", help="Path to rules text file")
    compile_parser.add_argument("--output", "-o", help="Output spec file")
    compile_parser.add_argument("--name", help="Game name")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a GameSpec")
    validate_parser.add_argument("spec_file", help="Path to spec file")

    # Play command
    play_parser = subparsers.add_parser("play", help="Start a game session")
    play_parser.add_argument("spec_file", help="Path to spec file")
    play_parser.add_argument("--bots", type=int, default=1, help="Number of bot players")

    # Innovation quick start
    innovation_parser = subparsers.add_parser("innovation", help="Quick start Innovation game")
    innovation_parser.add_argument("--bots", type=int, default=1, help="Number of bot players")

    args = parser.parse_args()

    if args.command == "compile":
        cmd_compile(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "play":
        cmd_play(args)
    elif args.command == "innovation":
        cmd_innovation(args)
    else:
        parser.print_help()
        sys.exit(1)


def cmd_compile(args):
    """Compile rules to GameSpec."""
    from .rule_compiler import RuleCompiler, CompilationStatus

    try:
        with open(args.rules_file, "r", encoding="utf-8") as f:
            rules_text = f.read()
    except FileNotFoundError:
        print(f"Error: File not found: {args.rules_file}")
        sys.exit(1)

    compiler = RuleCompiler()
    result = compiler.compile(rules_text, game_name=args.name)

    print(f"Compilation status: {result.status.value}")
    if result.spec:
        print(f"Game: {result.spec.game_name}")
        print(f"Players: {result.spec.min_players}-{result.spec.max_players}")
        print(f"Cards: {result.extracted_cards}")
        print(f"Actions: {result.extracted_actions}")

    if result.warnings:
        print("\nWarnings:")
        for w in result.warnings:
            print(f"  - {w}")

    if result.errors:
        print("\nErrors:")
        for e in result.errors:
            print(f"  - {e}")

    if result.status == CompilationStatus.FAILED:
        sys.exit(1)


def cmd_validate(args):
    """Validate a GameSpec."""
    print(f"Validating: {args.spec_file}")
    print("STUB: Spec loading not implemented")
    # STUB: Load and validate spec


def cmd_play(args):
    """Start a game session."""
    print(f"Starting game from: {args.spec_file}")
    print(f"With {args.bots} bot(s)")
    print("STUB: Interactive play not implemented")
    # STUB: Interactive session


def cmd_innovation(args):
    """Quick start Innovation game."""
    from .games.innovation.spec import create_innovation_spec
    from .session import SessionManager

    print("Starting Innovation game...")
    print(f"With {args.bots} automa(s)")

    spec = create_innovation_spec()
    manager = SessionManager()
    session = manager.create_session(spec, num_automas=args.bots)

    print(f"Session created: {session.session_id}")
    print("\nTo play:")
    print("1. Set up the physical game")
    print("2. Take a photo of the table")
    print("3. Follow the instructions")
    print("\nSTUB: Photo input not implemented in CLI")


if __name__ == "__main__":
    main()
