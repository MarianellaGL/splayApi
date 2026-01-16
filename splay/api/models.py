"""
API Models - Request and response schemas for mobile app.

These models define the contract between the mobile app and the engine.
All models are serializable to JSON.

Design principles:
- Mobile-friendly (minimal data transfer)
- Self-describing (includes metadata for UI rendering)
- Versioned (API version in responses)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# =============================================================================
# Enums for API
# =============================================================================

class APIVersion(Enum):
    V1 = "v1"


class SessionStatus(Enum):
    CREATED = "created"
    ACTIVE = "active"
    WAITING_PHOTO = "waiting_photo"
    WAITING_CORRECTION = "waiting_correction"
    AUTOMA_THINKING = "automa_thinking"
    YOUR_TURN = "your_turn"
    GAME_OVER = "game_over"


class CompilationStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CACHED = "cached"


class CorrectionType(Enum):
    CARD_IDENTITY = "card_identity"
    CARD_COUNT = "card_count"
    SPLAY_DIRECTION = "splay_direction"
    PLAYER_CONFIRMATION = "player_confirmation"
    ZONE_CONTENTS = "zone_contents"


# =============================================================================
# Shared Models (used in both requests and responses)
# =============================================================================

@dataclass
class CardInfo:
    """Card information for display."""
    card_id: str
    name: str
    age: int | None = None
    color: str | None = None
    image_url: str | None = None  # For card reference images


@dataclass
class ZoneInfo:
    """Zone information for display."""
    zone_id: str
    zone_type: str  # "hand", "board_pile", "score_pile", "achievement", "deck"
    card_count: int = 0
    top_card: CardInfo | None = None
    splay_direction: str | None = None  # For board piles
    visible_icons: dict[str, int] | None = None  # Icon counts


@dataclass
class PlayerInfo:
    """Player information for display."""
    player_id: str
    name: str
    is_human: bool
    is_current_turn: bool = False
    score: int = 0
    achievement_count: int = 0
    zones: list[ZoneInfo] = field(default_factory=list)


@dataclass
class QuestionInfo:
    """A question that needs user input."""
    question_id: str
    question_type: CorrectionType
    question_text: str
    options: list[dict[str, Any]] = field(default_factory=list)
    detected_value: Any = None
    is_required: bool = True
    hint: str | None = None


@dataclass
class InstructionInfo:
    """An instruction for the human player."""
    instruction_id: str
    text: str
    action_type: str | None = None  # "draw", "meld", "move", etc.
    source_zone: str | None = None
    target_zone: str | None = None
    card_reference: CardInfo | None = None
    is_complete: bool = False


# =============================================================================
# Request Models
# =============================================================================

@dataclass
class CompileRulesRequest:
    """
    Request to compile rules text into a GameSpec.

    POST /api/v1/compile
    """
    rules_text: str
    game_name: str | None = None
    faq_text: str | None = None
    force_recompile: bool = False


@dataclass
class CreateSessionRequest:
    """
    Request to create a new game session.

    POST /api/v1/sessions
    """
    spec_id: str | None = None  # Use cached spec
    rules_hash: str | None = None  # Alternative: look up by hash
    game_type: str = "innovation"  # For built-in games
    num_automas: int = 1
    human_player_name: str = "Player"
    bot_personalities: list[str] | None = None  # e.g., ["aggressive", "balanced"]
    random_seed: int | None = None


@dataclass
class UploadPhotoRequest:
    """
    Request to process a photo of the game table.

    POST /api/v1/sessions/{session_id}/photo

    The actual image is sent as multipart/form-data.
    This model contains the metadata.
    """
    session_id: str
    timestamp: float | None = None
    player_hints: dict[str, str] | None = None  # player_id -> position hint
    declared_hand: list[str] | None = None  # Card IDs if user declares hand


@dataclass
class SubmitCorrectionRequest:
    """
    Request to submit corrections for ambiguous detections.

    POST /api/v1/sessions/{session_id}/corrections
    """
    session_id: str
    corrections: dict[str, Any]  # question_id -> answer
    skip_remaining: bool = False  # Accept detected values for unanswered


@dataclass
class DeclareHandRequest:
    """
    Request to declare cards in hand (private zone).

    POST /api/v1/sessions/{session_id}/declare-hand
    """
    session_id: str
    card_ids: list[str]


@dataclass
class EndSessionRequest:
    """
    Request to end a game session.

    DELETE /api/v1/sessions/{session_id}
    """
    session_id: str
    reason: str = "user_ended"  # "user_ended", "game_complete", "abandoned"


# =============================================================================
# Response Models
# =============================================================================

@dataclass
class ErrorResponse:
    """
    Error response.

    Returned for any 4xx or 5xx status.
    """
    error: str
    error_code: str
    details: dict[str, Any] | None = None
    api_version: str = APIVersion.V1.value


@dataclass
class CompileRulesResponse:
    """
    Response from compiling rules.

    Returns the spec ID for creating sessions.
    """
    success: bool
    status: CompilationStatus
    spec_id: str | None = None
    rules_hash: str | None = None
    game_name: str | None = None
    player_count: tuple[int, int] | None = None  # (min, max)
    card_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    api_version: str = APIVersion.V1.value


@dataclass
class SessionResponse:
    """
    Response containing session information.

    Returned when creating or querying a session.
    """
    session_id: str
    status: SessionStatus
    game_name: str
    players: list[PlayerInfo] = field(default_factory=list)
    current_turn_player_id: str | None = None
    turn_number: int = 0
    created_at: float = 0.0
    api_version: str = APIVersion.V1.value


@dataclass
class GameStateResponse:
    """
    Complete game state for display.

    Returned after state changes.
    """
    session_id: str
    status: SessionStatus
    turn_number: int

    # Player states
    players: list[PlayerInfo] = field(default_factory=list)
    current_turn_player_id: str | None = None

    # Shared zones
    available_achievements: list[CardInfo] = field(default_factory=list)
    deck_sizes: dict[str, int] = field(default_factory=dict)  # "age_1" -> count

    # Game progress
    your_achievements: int = 0
    achievements_to_win: int = 6

    # Winner (if game over)
    winner: PlayerInfo | None = None
    game_over_reason: str | None = None

    api_version: str = APIVersion.V1.value


@dataclass
class PhotoResultResponse:
    """
    Response from processing a photo.

    May include:
    - Detected state
    - Questions needing answers
    - Instructions to execute
    """
    session_id: str
    success: bool
    status: SessionStatus

    # Detection results
    confidence: float = 0.0
    detected_changes: list[str] = field(default_factory=list)

    # If corrections needed
    questions: list[QuestionInfo] = field(default_factory=list)

    # If automa turns were processed
    automa_actions: list[str] = field(default_factory=list)

    # Instructions for human
    instructions: list[InstructionInfo] = field(default_factory=list)

    # Updated game state (if successful)
    game_state: GameStateResponse | None = None

    # Errors/warnings
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    api_version: str = APIVersion.V1.value


@dataclass
class InstructionsResponse:
    """
    Response containing instructions for the human player.

    Used when automa takes actions.
    """
    session_id: str
    instructions: list[InstructionInfo]
    automa_player: str | None = None
    summary: str | None = None  # "Bot 1 drew a card and melded Writing"
    next_action: str = "take_photo"  # What user should do next
    api_version: str = APIVersion.V1.value


@dataclass
class CorrectionResultResponse:
    """
    Response after submitting corrections.
    """
    session_id: str
    success: bool
    status: SessionStatus

    # If more corrections needed
    remaining_questions: list[QuestionInfo] = field(default_factory=list)

    # If successful, same as PhotoResultResponse
    automa_actions: list[str] = field(default_factory=list)
    instructions: list[InstructionInfo] = field(default_factory=list)
    game_state: GameStateResponse | None = None

    api_version: str = APIVersion.V1.value


# =============================================================================
# WebSocket Models (for real-time updates)
# =============================================================================

@dataclass
class WSMessage:
    """
    WebSocket message wrapper.

    All WS messages have a type and payload.
    """
    message_type: str
    payload: dict[str, Any]
    session_id: str | None = None
    timestamp: float = 0.0


class WSMessageType(Enum):
    # Client -> Server
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PING = "ping"

    # Server -> Client
    STATE_UPDATE = "state_update"
    INSTRUCTIONS = "instructions"
    QUESTION = "question"
    AUTOMA_THINKING = "automa_thinking"
    AUTOMA_ACTION = "automa_action"
    GAME_OVER = "game_over"
    ERROR = "error"
    PONG = "pong"
