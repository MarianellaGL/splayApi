"""
Session Module - Manages ephemeral game sessions.

A session represents one play-through of a game:
- Created when user starts a game
- Holds the current game state
- Processes photos and bot turns
- Destroyed when game ends

Sessions are EPHEMERAL:
- No persistence to database
- State reconstructed from photos
- Ends cleanly when game completes

The only persistence is cached compiled specs (by rules hash).
"""

from .manager import SessionManager, Session, SessionState
from .game_loop import GameLoop, LoopState, TurnResult

__all__ = [
    "SessionManager",
    "Session",
    "SessionState",
    "GameLoop",
    "LoopState",
    "TurnResult",
]
