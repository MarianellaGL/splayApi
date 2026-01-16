"""
Session Manager - Creates and manages game sessions.

LIFECYCLE (Non-Negotiable):
1. User uploads rules → compile to spec (cached by rules hash)
2. User starts session → create ephemeral session (in-memory only)
3. During game:
   - User takes photo of physical table
   - Vision proposes state (non-authoritative)
   - User corrects ambiguities
   - Engine validates and updates canonical state
   - Engine runs automa turns
   - App instructs human what to do physically
4. Game ends → session destroyed, ALL state deleted
5. User can:
   - Replay (reuse cached spec, new session)
   - New game (new rules, compile, new session)

PERSISTENCE RULES:
- NO database for gameplay
- Game state is ephemeral (session-scoped only)
- Only persistence: cached compiled specs (by rules hash)
- State must always be reconstructible from a new photo

AUTOMA CONSTRAINTS:
- Automa NEVER draws from hidden digital deck
- Automa only knows what's visible in photos
- Automa instructs human to move physical cards
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import uuid
import time

from ..spec_schema import GameSpec
from ..engine_core.state import GameState, GamePhase
from ..vision import VisionProcessor, StateReconciler, VisionStateProposal
from ..bots import BotPolicy


class SessionState(Enum):
    """State of a game session."""
    CREATED = "created"  # Session created, waiting for first photo
    ACTIVE = "active"  # Game in progress
    WAITING_INPUT = "waiting_input"  # Waiting for user correction
    AUTOMA_TURN = "automa_turn"  # Processing automa turns
    GAME_OVER = "game_over"  # Game completed
    ABANDONED = "abandoned"  # User quit


@dataclass
class Session:
    """
    An ephemeral game session.

    Contains:
    - The compiled spec (from cache or freshly compiled)
    - Current canonical game state
    - Vision processor
    - Bots for automas
    - Session metadata

    The session is destroyed when the game ends.
    State is NOT persisted.
    """
    session_id: str
    spec: GameSpec
    created_at: float

    # Current state
    state: SessionState = SessionState.CREATED
    game_state: GameState | None = None

    # Components
    vision_processor: VisionProcessor | None = None
    reconciler: StateReconciler | None = None
    bots: dict[str, BotPolicy] = field(default_factory=dict)

    # Turn tracking
    human_player_id: str | None = None
    current_turn_player: str | None = None
    turn_number: int = 0

    # Pending operations
    pending_proposal: VisionStateProposal | None = None
    pending_corrections: dict[str, Any] = field(default_factory=dict)

    # Instructions for human (from last automa turn)
    pending_instructions: list[str] = field(default_factory=list)

    # Session metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        """Check if session is still active."""
        return self.state in {
            SessionState.CREATED,
            SessionState.ACTIVE,
            SessionState.WAITING_INPUT,
            SessionState.AUTOMA_TURN,
        }

    def is_human_turn(self) -> bool:
        """Check if it's the human player's turn."""
        if not self.game_state:
            return False
        return self.game_state.current_player.player_id == self.human_player_id

    def get_instructions(self) -> list[str]:
        """Get pending instructions for human player."""
        instructions = self.pending_instructions.copy()
        self.pending_instructions.clear()
        return instructions


class SessionManager:
    """
    Manages game sessions.

    Responsibilities:
    - Create sessions from compiled specs
    - Track active sessions
    - Clean up completed sessions

    No persistence - sessions are in-memory only.
    """

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create_session(
        self,
        spec: GameSpec,
        human_player_id: str = "human",
        num_automas: int = 1,
        bot_configs: list[dict[str, Any]] | None = None,
    ) -> Session:
        """
        Create a new game session.

        Args:
            spec: Compiled game specification
            human_player_id: ID for the human player
            num_automas: Number of automa players
            bot_configs: Optional bot configuration

        Returns:
            New Session ready to start
        """
        from ..vision import InnovationVisionProcessor, InnovationVisionConfig
        from ..bots import InnovationBot, PERSONALITIES

        session_id = str(uuid.uuid4())

        # Create vision processor
        vision_processor = InnovationVisionProcessor(
            config=InnovationVisionConfig()
        )

        # Create reconciler
        reconciler = StateReconciler(spec=spec)

        # Create bots
        bots = {}
        personality_names = list(PERSONALITIES.keys())
        for i in range(num_automas):
            bot_id = f"bot_{i+1}"
            personality_name = personality_names[i % len(personality_names)]
            bot = InnovationBot(
                player_id=bot_id,
                personality=PERSONALITIES[personality_name],
            )
            bots[bot_id] = bot

        session = Session(
            session_id=session_id,
            spec=spec,
            created_at=time.time(),
            state=SessionState.CREATED,
            vision_processor=vision_processor,
            reconciler=reconciler,
            bots=bots,
            human_player_id=human_player_id,
        )

        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def end_session(self, session_id: str, reason: str = "completed"):
        """
        End a session and clean up.

        This is called when:
        - Game is completed
        - User abandons the game
        - Error occurs

        The session is removed from memory.
        No persistence.
        """
        session = self._sessions.pop(session_id, None)
        if session:
            if reason == "completed":
                session.state = SessionState.GAME_OVER
            else:
                session.state = SessionState.ABANDONED

            # Clear any state
            session.game_state = None
            session.pending_proposal = None
            session.pending_corrections.clear()
            session.pending_instructions.clear()

    def list_active_sessions(self) -> list[str]:
        """List IDs of active sessions."""
        return [
            sid for sid, session in self._sessions.items()
            if session.is_active()
        ]

    def cleanup_stale_sessions(self, max_age_seconds: int = 3600):
        """
        Clean up sessions older than max_age.

        Called periodically to free memory.
        """
        import time
        current_time = time.time()
        to_remove = []

        for session_id, session in self._sessions.items():
            age = current_time - session.created_at
            if age > max_age_seconds and not session.is_active():
                to_remove.append(session_id)

        for session_id in to_remove:
            self.end_session(session_id, reason="stale")
