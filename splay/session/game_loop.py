"""
Game Loop - The core photo-driven gameplay loop.

The loop:
1. User takes photo of table
2. Vision proposes state
3. User corrects ambiguities (fast UI)
4. Engine validates and updates canonical state
5. Engine runs N automa turns
6. App instructs human what to do
7. Repeat

Two photos per round are acceptable.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import Session
    from ..vision.proposal import PhotoInput, VisionStateProposal


class LoopState(Enum):
    """State of the game loop."""
    WAITING_PHOTO = "waiting_photo"
    PROCESSING_VISION = "processing_vision"
    WAITING_CORRECTION = "waiting_correction"
    RUNNING_AUTOMA = "running_automa"
    WAITING_HUMAN_ACTION = "waiting_human_action"
    GAME_OVER = "game_over"


@dataclass
class TurnResult:
    """
    Result of processing a turn.

    Contains instructions for the human player
    and any questions that need answering.
    """
    success: bool
    loop_state: LoopState

    # Instructions for human to execute on physical table
    instructions: list[str] = field(default_factory=list)

    # Questions for user (ambiguities, confirmations)
    questions: list[dict[str, Any]] = field(default_factory=list)

    # Changes detected from photo
    detected_changes: list[str] = field(default_factory=list)

    # Automa actions taken
    automa_actions: list[str] = field(default_factory=list)

    # Errors/warnings
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Game over info
    winner: str | None = None


class GameLoop:
    """
    The main game loop driver.

    Usage:
        loop = GameLoop(session)

        # Photo comes in
        result = loop.process_photo(photo)

        if result.questions:
            # Show questions to user, get answers
            answers = get_user_answers(result.questions)
            result = loop.apply_corrections(answers)

        # Show instructions to user
        show_instructions(result.instructions)

        # Wait for next photo...
    """

    def __init__(self, session: Session):
        self.session = session
        self.state = LoopState.WAITING_PHOTO

    def process_photo(self, photo: PhotoInput) -> TurnResult:
        """
        Process a photo of the game table.

        Steps:
        1. Run vision processor
        2. Reconcile with canonical state
        3. If uncertainties, return questions
        4. If valid, run automa turns
        5. Return instructions
        """
        from ..vision.proposal import PhotoInput
        from .manager import SessionState

        # Vision processing
        self.state = LoopState.PROCESSING_VISION

        if not self.session.vision_processor:
            return TurnResult(
                success=False,
                loop_state=self.state,
                errors=["No vision processor configured"],
            )

        # Get vision proposal
        proposal = self.session.vision_processor.process(photo)
        self.session.pending_proposal = proposal

        # Reconcile with canonical state
        if not self.session.reconciler or not self.session.game_state:
            # First photo - initialize state from vision
            return self._initialize_from_vision(proposal)

        reconciliation = self.session.reconciler.reconcile(
            proposal, self.session.game_state
        )

        if reconciliation.needs_user_input:
            self.state = LoopState.WAITING_CORRECTION
            return TurnResult(
                success=True,
                loop_state=self.state,
                questions=reconciliation.get_questions(),
                detected_changes=reconciliation.changes_detected,
                warnings=[str(c) for c in reconciliation.conflicts],
            )

        # Reconciliation successful - update state
        if reconciliation.new_state:
            self.session.game_state = reconciliation.new_state

        # Run automa turns if needed
        return self._run_automa_turns()

    def apply_corrections(self, corrections: dict[str, Any]) -> TurnResult:
        """
        Apply user corrections to pending proposal.

        Called after user answers questions about ambiguities.
        """
        if not self.session.pending_proposal:
            return TurnResult(
                success=False,
                loop_state=self.state,
                errors=["No pending proposal to correct"],
            )

        # Apply corrections to proposal
        corrected_proposal = self.session.pending_proposal.apply_corrections(
            corrections
        )
        self.session.pending_proposal = corrected_proposal

        # Re-reconcile
        if self.session.reconciler and self.session.game_state:
            reconciliation = self.session.reconciler.apply_corrections(
                self.session.reconciler.reconcile(
                    corrected_proposal, self.session.game_state
                ),
                corrections,
            )

            if reconciliation.needs_user_input:
                return TurnResult(
                    success=True,
                    loop_state=LoopState.WAITING_CORRECTION,
                    questions=reconciliation.get_questions(),
                )

            if reconciliation.new_state:
                self.session.game_state = reconciliation.new_state

        # Run automa turns
        return self._run_automa_turns()

    def _initialize_from_vision(self, proposal: VisionStateProposal) -> TurnResult:
        """
        Initialize game state from first vision proposal.

        For MVP, we'll ask user to confirm player setup.
        """
        from ..games.innovation.state import InnovationState
        from ..engine_core.state import GamePhase

        # Create initial state based on detected players
        player_names = []

        # Always have human player
        player_names.append((
            self.session.human_player_id or "human",
            "Human Player",
            True,
        ))

        # Add detected/configured bots
        for bot_id in self.session.bots.keys():
            player_names.append((bot_id, f"Automa {bot_id}", False))

        self.session.game_state = InnovationState.create(
            game_id=self.session.session_id,
            spec_id=self.session.spec.game_id,
            player_names=player_names,
        )

        # Transition to playing
        self.session.game_state = self.session.game_state._copy_with(
            phase=GamePhase.PLAYING,
            actions_remaining=1,  # First turn: 1 action
        )

        self.state = LoopState.WAITING_HUMAN_ACTION

        return TurnResult(
            success=True,
            loop_state=self.state,
            instructions=[
                "Game initialized!",
                "Take your turn, then take a photo of the table.",
            ],
            detected_changes=["Game state initialized from photo"],
        )

    def _run_automa_turns(self) -> TurnResult:
        """
        Run automa turns until it's human's turn again.
        """
        from ..engine_core.action_generator import legal_actions
        from ..engine_core.reducer import apply_action
        from ..engine_core.action import ActionType

        if not self.session.game_state:
            return TurnResult(
                success=False,
                loop_state=self.state,
                errors=["No game state"],
            )

        self.state = LoopState.RUNNING_AUTOMA
        all_instructions: list[str] = []
        all_actions: list[str] = []

        # Run automa turns
        max_turns = 10  # Safety limit
        turns_run = 0

        while turns_run < max_turns:
            current_player = self.session.game_state.current_player

            # Check if human's turn
            if current_player.player_id == self.session.human_player_id:
                break

            # Check for game over
            if self.session.game_state.phase.value == "game_over":
                self.state = LoopState.GAME_OVER
                return TurnResult(
                    success=True,
                    loop_state=self.state,
                    instructions=all_instructions,
                    automa_actions=all_actions,
                    winner=self._determine_winner(),
                )

            # Get bot for this player
            bot = self.session.bots.get(current_player.player_id)
            if not bot:
                # No bot - skip to next player
                # STUB: Handle end turn
                break

            # Generate and execute bot actions
            legal = legal_actions(self.session.spec, self.session.game_state)
            if not legal:
                break

            decision = bot.select_action(
                self.session.game_state,
                self.session.spec,
                legal,
            )

            # Apply action
            result = apply_action(
                self.session.spec,
                self.session.game_state,
                decision.action,
            )

            if result.success and result.new_state:
                self.session.game_state = result.new_state
                all_instructions.extend(decision.physical_instructions)
                all_actions.append(
                    f"{current_player.name}: {decision.action.action_type.value}"
                )

                # Handle end of turn
                if decision.action.action_type == ActionType.END_TURN:
                    turns_run += 1
            else:
                # Action failed - shouldn't happen with legal actions
                break

        # Set expected changes for next reconciliation
        if self.session.reconciler and all_actions:
            self.session.reconciler.set_expected_changes(all_actions)

        self.state = LoopState.WAITING_HUMAN_ACTION

        return TurnResult(
            success=True,
            loop_state=self.state,
            instructions=all_instructions + [
                "Your turn! Make your moves and take a photo.",
            ],
            automa_actions=all_actions,
        )

    def _determine_winner(self) -> str | None:
        """Determine game winner."""
        if not self.session.game_state:
            return None

        # Check achievements
        target = {2: 6, 3: 5, 4: 4}.get(self.session.game_state.num_players, 6)
        for player in self.session.game_state.players:
            if player.achievements.count >= target:
                return player.player_id

        return None
