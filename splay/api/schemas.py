"""
Pydantic Schemas for API - Proper request/response models for OpenAPI.

These models define the exact contract between the mobile app and the engine.
All responses include explicit types for OpenAPI schema generation.

Error Codes:
- PHOTO_UNREADABLE: Photo could not be processed (corrupt, too dark, etc.)
- LOW_CONFIDENCE: Vision confidence below threshold, requires correction
- INVALID_CORRECTION: Submitted correction value is invalid
- INVALID_SPEC_ID: Spec ID not found or invalid
- SESSION_NOT_FOUND: Session does not exist or has expired
"""

from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class SessionStatus(str, Enum):
    """Session status values."""
    CREATED = "created"
    ACTIVE = "active"
    WAITING_PHOTO = "waiting_photo"
    WAITING_CORRECTION = "waiting_correction"
    AUTOMA_THINKING = "automa_thinking"
    YOUR_TURN = "your_turn"
    GAME_OVER = "game_over"


class CompilationStatus(str, Enum):
    """Rule compilation status."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CACHED = "cached"


class CorrectionType(str, Enum):
    """Types of corrections needed."""
    CARD_IDENTITY = "card_identity"
    CARD_COUNT = "card_count"
    SPLAY_DIRECTION = "splay_direction"
    PLAYER_CONFIRMATION = "player_confirmation"
    ZONE_CONTENTS = "zone_contents"


class ConfidenceLevel(str, Enum):
    """Vision confidence levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


class SplayDirection(str, Enum):
    """Splay directions for board piles."""
    NONE = "none"
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    UNKNOWN = "unknown"


class ErrorCode(str, Enum):
    """Structured error codes."""
    PHOTO_UNREADABLE = "PHOTO_UNREADABLE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    INVALID_CORRECTION = "INVALID_CORRECTION"
    INVALID_SPEC_ID = "INVALID_SPEC_ID"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# =============================================================================
# Shared Models
# =============================================================================

class CardInfo(BaseModel):
    """Card information for display."""
    card_id: str
    name: str
    age: Optional[int] = None
    color: Optional[str] = None
    image_url: Optional[str] = None

    model_config = {"from_attributes": True}


class ZoneInfo(BaseModel):
    """Zone information for display."""
    zone_id: str
    zone_type: str = Field(description="hand, board_pile, score_pile, achievement, deck")
    card_count: int = 0
    top_card: Optional[CardInfo] = None
    splay_direction: Optional[str] = None
    visible_icons: Optional[dict[str, int]] = None

    model_config = {"from_attributes": True}


class PlayerInfo(BaseModel):
    """Player information for display."""
    player_id: str
    name: str
    is_human: bool
    is_current_turn: bool = False
    score: int = 0
    achievement_count: int = 0
    zones: list[ZoneInfo] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class QuestionInfo(BaseModel):
    """A question that needs user input for disambiguation."""
    question_id: str
    question_type: CorrectionType
    question_text: str
    options: list[dict[str, Any]] = Field(default_factory=list)
    detected_value: Optional[Any] = None
    is_required: bool = True
    hint: Optional[str] = None


class InstructionInfo(BaseModel):
    """An instruction for the human player to execute physically."""
    instruction_id: str
    text: str
    action_type: Optional[str] = Field(None, description="draw, meld, move, etc.")
    source_zone: Optional[str] = None
    target_zone: Optional[str] = None
    card_reference: Optional[CardInfo] = None
    is_complete: bool = False


# =============================================================================
# Vision Models (for /photo response)
# =============================================================================

class DetectedCard(BaseModel):
    """A card detected from the photo."""
    detected_age: Optional[int] = None
    detected_color: Optional[str] = None
    detected_name: Optional[str] = None
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    confidence_score: float = Field(0.5, ge=0.0, le=1.0)
    bounding_box: Optional[tuple[int, int, int, int]] = Field(
        None, description="x, y, width, height in pixels"
    )
    matched_card_id: Optional[str] = None


class DetectedZone(BaseModel):
    """A detected zone (pile, hand, etc.) from the photo."""
    zone_type: str = Field(description="board_pile, hand, score_pile, achievement, deck")
    player_id: Optional[str] = None
    color: Optional[str] = None
    cards: list[DetectedCard] = Field(default_factory=list)
    splay_direction: SplayDirection = SplayDirection.UNKNOWN
    card_count: Optional[int] = None
    card_count_approximate: bool = True
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


class DetectedPlayer(BaseModel):
    """Detected state for a single player."""
    player_id: str
    player_position: Optional[str] = Field(None, description="top, bottom, left, right")
    board_piles: dict[str, DetectedZone] = Field(default_factory=dict)
    score_pile: Optional[DetectedZone] = None
    score_pile_count: Optional[int] = None
    achievements: list[DetectedCard] = Field(default_factory=list)
    hand: Optional[DetectedZone] = None
    hand_count: Optional[int] = None
    hand_declared: bool = False


class UncertaintyInfo(BaseModel):
    """A zone where vision is uncertain and needs user confirmation."""
    zone_id: str
    zone_type: str
    uncertainty_type: str = Field(description="card_identity, card_count, splay_direction")
    question: str
    player_id: Optional[str] = None
    detected_value: Optional[Any] = None
    alternatives: list[Any] = Field(default_factory=list)


# =============================================================================
# Request Models
# =============================================================================

class CompileRequest(BaseModel):
    """Request to compile rules text into a GameSpec."""
    rules_text: str = Field(..., description="Full rules text to compile")
    game_name: Optional[str] = Field(None, description="Name for the game")
    faq_text: Optional[str] = Field(None, description="Optional FAQ/errata text")
    force_recompile: bool = Field(False, description="Force recompilation even if cached")


class CreateSessionRequest(BaseModel):
    """Request to create a new game session."""
    game_type: str = Field("innovation", description="Built-in game type")
    num_automas: int = Field(1, ge=1, le=3, description="Number of AI opponents")
    human_player_name: str = Field("Player", description="Display name for human player")
    spec_id: Optional[str] = Field(None, description="Use a previously compiled spec")
    bot_personalities: Optional[list[str]] = Field(
        None, description="Personality for each bot: aggressive, balanced, defensive"
    )
    random_seed: Optional[int] = Field(None, description="Seed for reproducible games")


class PlayerHints(BaseModel):
    """Hints about player positions in the photo."""
    player_positions: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of player_id to position (top, bottom, left, right)"
    )


class Correction(BaseModel):
    """A single correction for an uncertainty."""
    question_id: str = Field(..., description="ID of the question being answered")
    value: Any = Field(..., description="The corrected value")


class CorrectionsRequest(BaseModel):
    """Request to submit corrections for ambiguous detections."""
    corrections: list[Correction] = Field(
        ..., description="List of corrections to apply"
    )
    skip_remaining: bool = Field(
        False, description="Accept detected values for unanswered questions"
    )


# =============================================================================
# Response Models
# =============================================================================

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str = Field(..., description="Human-readable error message")
    error_code: ErrorCode = Field(..., description="Machine-readable error code")
    details: Optional[dict[str, Any]] = Field(None, description="Additional error context")
    api_version: str = Field("v1", description="API version")


class CompileResponse(BaseModel):
    """Response from compiling rules."""
    success: bool
    status: CompilationStatus
    spec_id: Optional[str] = Field(None, description="ID for creating sessions")
    rules_hash: Optional[str] = Field(None, description="Hash of the rules text")
    game_name: Optional[str] = None
    player_count_min: Optional[int] = None
    player_count_max: Optional[int] = None
    card_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    api_version: str = "v1"


class SessionResponse(BaseModel):
    """Response containing session information."""
    session_id: str
    status: SessionStatus
    game_name: str
    players: list[PlayerInfo] = Field(default_factory=list)
    current_turn_player_id: Optional[str] = None
    turn_number: int = 0
    created_at: float = 0.0
    api_version: str = "v1"


class GameStateResponse(BaseModel):
    """Complete game state for display."""
    session_id: str
    status: SessionStatus
    turn_number: int
    players: list[PlayerInfo] = Field(default_factory=list)
    current_turn_player_id: Optional[str] = None
    available_achievements: list[CardInfo] = Field(default_factory=list)
    deck_sizes: dict[str, int] = Field(default_factory=dict)
    your_achievements: int = 0
    achievements_to_win: int = 6
    winner: Optional[PlayerInfo] = None
    game_over_reason: Optional[str] = None
    api_version: str = "v1"


class VisionStateProposal(BaseModel):
    """
    Complete state proposal from vision processing.

    This is returned from POST /photo endpoint.
    If requires_confirmation is true, corrections must be submitted before automa runs.
    If requires_confirmation is false, automa_instructions are included immediately.
    """
    proposal_id: str = Field(..., description="Unique ID for this proposal")
    session_id: str
    timestamp: float

    # Confidence
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel

    # Detection results
    players: list[DetectedPlayer] = Field(default_factory=list)
    achievements_available: list[DetectedCard] = Field(default_factory=list)
    deck_sizes: dict[str, int] = Field(default_factory=dict)

    # Uncertainties requiring correction
    uncertainties: list[UncertaintyInfo] = Field(default_factory=list)
    requires_confirmation: bool = Field(
        False,
        description="If true, /corrections must be called before automa runs"
    )

    # Automa results (populated if requires_confirmation=false)
    automa_executed: bool = Field(
        False, description="Whether automa turn was computed"
    )
    automa_actions: list[str] = Field(
        default_factory=list, description="Description of automa actions taken"
    )
    automa_instructions: list[InstructionInfo] = Field(
        default_factory=list, description="Instructions for human to execute"
    )

    # Game state after processing
    game_state: Optional[GameStateResponse] = None

    # Validation
    validation_errors: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)

    api_version: str = "v1"


class InstructionsResponse(BaseModel):
    """Response containing pending instructions for the human player."""
    session_id: str
    instructions: list[InstructionInfo]
    automa_player: Optional[str] = Field(None, description="Which automa took actions")
    summary: Optional[str] = Field(
        None, description="Human-readable summary: 'Bot 1 drew a card and melded Writing'"
    )
    next_action: str = Field(
        "take_photo", description="What user should do next: take_photo, execute_then_photo"
    )
    api_version: str = "v1"


class CorrectionsResponse(BaseModel):
    """Response after submitting corrections."""
    session_id: str
    success: bool
    status: SessionStatus

    # If more corrections needed
    remaining_questions: list[QuestionInfo] = Field(default_factory=list)

    # If all corrections resolved, automa runs automatically
    automa_executed: bool = False
    automa_actions: list[str] = Field(default_factory=list)
    automa_instructions: list[InstructionInfo] = Field(default_factory=list)

    # Updated game state
    game_state: Optional[GameStateResponse] = None

    api_version: str = "v1"


class SessionListResponse(BaseModel):
    """Response listing active sessions."""
    sessions: list[str]
    count: int


class EndSessionResponse(BaseModel):
    """Response after ending a session."""
    success: bool
    session_id: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str
