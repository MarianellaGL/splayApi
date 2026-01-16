"""
API Service - Business logic layer between API and engine.

The service:
1. Translates API requests to engine calls
2. Manages sessions
3. Handles photo processing
4. Formats responses for mobile

This layer is framework-agnostic (can be used with FastAPI, Flask, etc.)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import time
import base64

from .models import (
    # Requests
    CompileRulesRequest,
    CreateSessionRequest,
    UploadPhotoRequest,
    SubmitCorrectionRequest,
    # Responses
    CompileRulesResponse,
    SessionResponse,
    GameStateResponse,
    PhotoResultResponse,
    InstructionsResponse,
    CorrectionResultResponse,
    ErrorResponse,
    # Shared
    PlayerInfo,
    ZoneInfo,
    CardInfo,
    QuestionInfo,
    InstructionInfo,
    # Enums
    SessionStatus,
    CompilationStatus,
    CorrectionType,
)
from ..session import SessionManager, Session, GameLoop, LoopState
from ..rule_compiler import RuleCompiler, CompilationResult
from ..vision.proposal import PhotoInput
from ..games.innovation.spec import create_innovation_spec


@dataclass
class APIService:
    """
    Main API service for mobile app.

    Usage:
        service = APIService()

        # Compile rules
        response = service.compile_rules(request)

        # Create session
        session_response = service.create_session(request)

        # Process photo
        photo_response = service.process_photo(session_id, image_bytes)
    """
    session_manager: SessionManager = field(default_factory=SessionManager)
    rule_compiler: RuleCompiler = field(default_factory=RuleCompiler)

    # Cache of compiled specs by ID
    _specs: dict[str, Any] = field(default_factory=dict)

    # Game loops per session
    _game_loops: dict[str, GameLoop] = field(default_factory=dict)

    def compile_rules(self, request: CompileRulesRequest) -> CompileRulesResponse:
        """
        Compile rules text into a GameSpec.

        Returns spec_id that can be used to create sessions.
        """
        result = self.rule_compiler.compile(
            rules_text=request.rules_text,
            game_name=request.game_name,
            faq_text=request.faq_text,
            force_recompile=request.force_recompile,
        )

        if result.status == CompilationResult.status:
            status = CompilationStatus.FAILED
        else:
            status = CompilationStatus(result.status.value)

        spec_id = None
        if result.spec:
            spec_id = result.spec.game_id
            self._specs[spec_id] = result.spec

        return CompileRulesResponse(
            success=result.status.value != "failed",
            status=status,
            spec_id=spec_id,
            rules_hash=result.rules_hash,
            game_name=result.spec.game_name if result.spec else None,
            player_count=(
                (result.spec.min_players, result.spec.max_players)
                if result.spec else None
            ),
            card_count=result.extracted_cards,
            warnings=result.warnings,
            errors=result.errors,
        )

    def create_session(self, request: CreateSessionRequest) -> SessionResponse:
        """
        Create a new game session.
        """
        # Get spec
        if request.game_type == "innovation":
            spec = create_innovation_spec()
        elif request.spec_id and request.spec_id in self._specs:
            spec = self._specs[request.spec_id]
        else:
            raise ValueError(f"Unknown game type or spec: {request.game_type}")

        # Create session
        session = self.session_manager.create_session(
            spec=spec,
            human_player_id="human",
            num_automas=request.num_automas,
        )

        # Create game loop
        game_loop = GameLoop(session)
        self._game_loops[session.session_id] = game_loop

        return self._session_to_response(session)

    def get_session(self, session_id: str) -> SessionResponse | ErrorResponse:
        """
        Get session status.
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            return ErrorResponse(
                error="Session not found",
                error_code="SESSION_NOT_FOUND",
            )
        return self._session_to_response(session)

    def process_photo(
        self,
        session_id: str,
        image_data: bytes,
        metadata: UploadPhotoRequest | None = None,
    ) -> PhotoResultResponse:
        """
        Process a photo of the game table.

        This is the main game loop entry point.
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            return PhotoResultResponse(
                session_id=session_id,
                success=False,
                status=SessionStatus.CREATED,
                errors=["Session not found"],
            )

        game_loop = self._game_loops.get(session_id)
        if not game_loop:
            return PhotoResultResponse(
                session_id=session_id,
                success=False,
                status=SessionStatus.CREATED,
                errors=["Game loop not initialized"],
            )

        # Create photo input
        photo = PhotoInput(
            image_data=image_data,
            timestamp=metadata.timestamp if metadata else time.time(),
            player_positions=metadata.player_hints if metadata else None,
        )

        # Process through game loop
        result = game_loop.process_photo(photo)

        # Convert to API response
        return self._turn_result_to_response(session_id, session, result)

    def submit_corrections(
        self,
        request: SubmitCorrectionRequest,
    ) -> CorrectionResultResponse:
        """
        Submit corrections for ambiguous detections.
        """
        session = self.session_manager.get_session(request.session_id)
        if not session:
            return CorrectionResultResponse(
                session_id=request.session_id,
                success=False,
                status=SessionStatus.CREATED,
            )

        game_loop = self._game_loops.get(request.session_id)
        if not game_loop:
            return CorrectionResultResponse(
                session_id=request.session_id,
                success=False,
                status=SessionStatus.CREATED,
            )

        # Apply corrections
        result = game_loop.apply_corrections(request.corrections)

        # Convert questions
        remaining_questions = []
        if result.questions:
            for q in result.questions:
                remaining_questions.append(
                    QuestionInfo(
                        question_id=q.get("id", ""),
                        question_type=CorrectionType.CARD_IDENTITY,
                        question_text=q.get("question", ""),
                        options=q.get("options", q.get("alternatives", [])),
                        detected_value=q.get("detected_value"),
                    )
                )

        return CorrectionResultResponse(
            session_id=request.session_id,
            success=result.success,
            status=self._loop_state_to_status(result.loop_state),
            remaining_questions=remaining_questions,
            automa_actions=result.automa_actions,
            instructions=self._convert_instructions(result.instructions),
            game_state=self._build_game_state(request.session_id, session),
        )

    def get_game_state(self, session_id: str) -> GameStateResponse | ErrorResponse:
        """
        Get current game state.
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            return ErrorResponse(
                error="Session not found",
                error_code="SESSION_NOT_FOUND",
            )

        return self._build_game_state(session_id, session)

    def get_instructions(self, session_id: str) -> InstructionsResponse | ErrorResponse:
        """
        Get pending instructions for the human player.
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            return ErrorResponse(
                error="Session not found",
                error_code="SESSION_NOT_FOUND",
            )

        instructions = session.get_instructions()
        return InstructionsResponse(
            session_id=session_id,
            instructions=self._convert_instructions(instructions),
            next_action="take_photo" if not instructions else "execute_then_photo",
        )

    def end_session(self, session_id: str, reason: str = "user_ended") -> bool:
        """
        End a game session.
        """
        self.session_manager.end_session(session_id, reason)
        self._game_loops.pop(session_id, None)
        return True

    def list_sessions(self) -> list[str]:
        """
        List active session IDs.
        """
        return self.session_manager.list_active_sessions()

    # =========================================================================
    # Helper methods
    # =========================================================================

    def _session_to_response(self, session: Session) -> SessionResponse:
        """Convert Session to SessionResponse."""
        players = []
        if session.game_state:
            for player in session.game_state.players:
                players.append(
                    PlayerInfo(
                        player_id=player.player_id,
                        name=player.name,
                        is_human=player.is_human,
                        is_current_turn=(
                            player.player_id ==
                            session.game_state.current_player.player_id
                        ),
                        score=len(player.score_pile.cards),
                        achievement_count=player.achievements.count,
                    )
                )

        return SessionResponse(
            session_id=session.session_id,
            status=self._session_state_to_status(session),
            game_name=session.spec.game_name,
            players=players,
            current_turn_player_id=(
                session.game_state.current_player.player_id
                if session.game_state else None
            ),
            turn_number=session.turn_number,
            created_at=session.created_at,
        )

    def _session_state_to_status(self, session: Session) -> SessionStatus:
        """Convert session state to API status."""
        from ..session.manager import SessionState

        mapping = {
            SessionState.CREATED: SessionStatus.CREATED,
            SessionState.ACTIVE: SessionStatus.ACTIVE,
            SessionState.WAITING_INPUT: SessionStatus.WAITING_CORRECTION,
            SessionState.AUTOMA_TURN: SessionStatus.AUTOMA_THINKING,
            SessionState.GAME_OVER: SessionStatus.GAME_OVER,
            SessionState.ABANDONED: SessionStatus.GAME_OVER,
        }
        return mapping.get(session.state, SessionStatus.ACTIVE)

    def _loop_state_to_status(self, loop_state: LoopState) -> SessionStatus:
        """Convert loop state to API status."""
        mapping = {
            LoopState.WAITING_PHOTO: SessionStatus.WAITING_PHOTO,
            LoopState.PROCESSING_VISION: SessionStatus.ACTIVE,
            LoopState.WAITING_CORRECTION: SessionStatus.WAITING_CORRECTION,
            LoopState.RUNNING_AUTOMA: SessionStatus.AUTOMA_THINKING,
            LoopState.WAITING_HUMAN_ACTION: SessionStatus.YOUR_TURN,
            LoopState.GAME_OVER: SessionStatus.GAME_OVER,
        }
        return mapping.get(loop_state, SessionStatus.ACTIVE)

    def _turn_result_to_response(
        self,
        session_id: str,
        session: Session,
        result,
    ) -> PhotoResultResponse:
        """Convert TurnResult to PhotoResultResponse."""
        # Convert questions
        questions = []
        for q in result.questions:
            questions.append(
                QuestionInfo(
                    question_id=q.get("id", ""),
                    question_type=CorrectionType.CARD_IDENTITY,
                    question_text=q.get("question", ""),
                    options=q.get("options", q.get("alternatives", [])),
                    detected_value=q.get("detected_value"),
                )
            )

        return PhotoResultResponse(
            session_id=session_id,
            success=result.success,
            status=self._loop_state_to_status(result.loop_state),
            detected_changes=result.detected_changes,
            questions=questions,
            automa_actions=result.automa_actions,
            instructions=self._convert_instructions(result.instructions),
            game_state=self._build_game_state(session_id, session),
            errors=result.errors,
            warnings=result.warnings,
        )

    def _build_game_state(
        self,
        session_id: str,
        session: Session,
    ) -> GameStateResponse:
        """Build complete game state response."""
        players = []
        if session.game_state:
            for player in session.game_state.players:
                zones = self._build_player_zones(player, session.spec)
                players.append(
                    PlayerInfo(
                        player_id=player.player_id,
                        name=player.name,
                        is_human=player.is_human,
                        is_current_turn=(
                            player.player_id ==
                            session.game_state.current_player.player_id
                        ),
                        score=len(player.score_pile.cards),
                        achievement_count=player.achievements.count,
                        zones=zones,
                    )
                )

        # Achievements
        achievements = []
        if session.game_state:
            for card in session.game_state.achievements.cards:
                card_def = session.spec.get_card(card.card_id)
                achievements.append(
                    CardInfo(
                        card_id=card.card_id,
                        name=card_def.name if card_def else card.card_id,
                        age=card_def.age if card_def else None,
                    )
                )

        # Deck sizes
        deck_sizes = {}
        if session.game_state:
            for key, deck in session.game_state.supply_decks.items():
                deck_sizes[key] = deck.count

        # Win condition
        num_players = len(players) if players else 2
        achievements_to_win = {2: 6, 3: 5, 4: 4}.get(num_players, 6)

        return GameStateResponse(
            session_id=session_id,
            status=self._session_state_to_status(session),
            turn_number=session.turn_number,
            players=players,
            current_turn_player_id=(
                session.game_state.current_player.player_id
                if session.game_state else None
            ),
            available_achievements=achievements,
            deck_sizes=deck_sizes,
            your_achievements=(
                session.game_state.get_player(session.human_player_id).achievements.count
                if session.game_state and session.human_player_id else 0
            ),
            achievements_to_win=achievements_to_win,
        )

    def _build_player_zones(self, player, spec) -> list[ZoneInfo]:
        """Build zone info for a player."""
        zones = []

        # Hand
        zones.append(
            ZoneInfo(
                zone_id=f"{player.player_id}_hand",
                zone_type="hand",
                card_count=player.hand.count,
            )
        )

        # Score pile
        zones.append(
            ZoneInfo(
                zone_id=f"{player.player_id}_score",
                zone_type="score_pile",
                card_count=player.score_pile.count,
            )
        )

        # Board piles
        for color, stack in player.board.items():
            top_card = None
            if stack.top_card:
                card_def = spec.get_card(stack.top_card.card_id)
                top_card = CardInfo(
                    card_id=stack.top_card.card_id,
                    name=card_def.name if card_def else stack.top_card.card_id,
                    age=card_def.age if card_def else None,
                    color=color,
                )

            zones.append(
                ZoneInfo(
                    zone_id=f"{player.player_id}_board_{color}",
                    zone_type="board_pile",
                    card_count=len(stack.cards),
                    top_card=top_card,
                    splay_direction=stack.splay_direction.value,
                )
            )

        return zones

    def _convert_instructions(self, instructions: list[str]) -> list[InstructionInfo]:
        """Convert string instructions to InstructionInfo."""
        result = []
        for i, text in enumerate(instructions):
            result.append(
                InstructionInfo(
                    instruction_id=f"inst_{i}",
                    text=text,
                )
            )
        return result
