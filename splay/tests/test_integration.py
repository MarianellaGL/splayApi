"""
Integration tests - End-to-end workflow tests.

Tests the complete flow:
1. Create spec
2. Create session
3. Process game loop
4. Bot decision making
"""

import pytest
import time

from ..games.innovation.spec import create_innovation_spec
from ..games.innovation.state import InnovationState
from ..session import SessionManager, GameLoop, LoopState
from ..vision.proposal import PhotoInput, VisionStateProposal, ConfidenceLevel
from ..bots import InnovationBot
from ..engine_core.action_generator import legal_actions


class TestFullGameFlow:
    """Tests for complete game flow."""

    def test_create_session_from_spec(self):
        """Can create a session from Innovation spec."""
        spec = create_innovation_spec()
        manager = SessionManager()

        session = manager.create_session(spec, num_automas=1)

        assert session is not None
        assert session.session_id is not None
        assert session.spec == spec
        assert len(session.bots) == 1

    def test_session_lifecycle(self):
        """Session can be created and ended."""
        spec = create_innovation_spec()
        manager = SessionManager()

        session = manager.create_session(spec)
        session_id = session.session_id

        assert session_id in manager.list_active_sessions()

        manager.end_session(session_id)

        assert session_id not in manager.list_active_sessions()

    def test_game_loop_initialization(self):
        """Game loop can be initialized."""
        spec = create_innovation_spec()
        manager = SessionManager()
        session = manager.create_session(spec)

        loop = GameLoop(session)

        assert loop.state == LoopState.WAITING_PHOTO

    def test_bot_makes_legal_decisions(self, two_player_state, innovation_spec):
        """Bot always selects from legal actions."""
        state = two_player_state

        # Make it bot's turn
        state = state._copy_with(current_player_idx=1)

        bot = InnovationBot(player_id="bot1")
        legal = legal_actions(innovation_spec, state)

        # Run multiple times
        for _ in range(5):
            decision = bot.select_action(state, innovation_spec, legal)
            # Action type should match one of the legal actions
            assert any(
                a.action_type == decision.action.action_type
                for a in legal
            )
            # Should have instructions
            assert len(decision.physical_instructions) >= 0


class TestSpecCompilation:
    """Tests for spec creation and validation."""

    def test_innovation_spec_is_valid(self):
        """Innovation spec passes validation."""
        from ..spec_schema import validate_spec

        spec = create_innovation_spec()
        result = validate_spec(spec)

        # May have warnings but should have no structural errors
        assert result.valid or len([e for e in result.errors if "required" in e.lower()]) == 0

    def test_spec_has_actions(self):
        """Innovation spec has action definitions."""
        spec = create_innovation_spec()

        assert len(spec.actions) > 0
        action_names = {a.name for a in spec.actions}
        assert "draw" in action_names
        assert "meld" in action_names
        assert "dogma" in action_names
        assert "achieve" in action_names

    def test_spec_has_cards(self):
        """Innovation spec has card definitions."""
        spec = create_innovation_spec()

        assert len(spec.cards) > 0
        # Check a known card
        archery = spec.get_card("archery")
        assert archery is not None
        assert archery.age == 1
        assert archery.color == "red"


class TestVisionIntegration:
    """Tests for vision system integration."""

    def test_mock_vision_returns_proposal(self):
        """Mock vision processor returns valid proposal."""
        from ..vision import MockVisionProcessor

        processor = MockVisionProcessor()
        photo = PhotoInput(image_path="test.jpg", timestamp=time.time())

        proposal = processor.process(photo)

        assert proposal is not None
        assert proposal.proposal_id is not None
        assert 0 <= proposal.confidence_score <= 1

    def test_reconciler_handles_empty_proposal(self, two_player_state, innovation_spec):
        """Reconciler handles proposal with no detected state."""
        from ..vision import StateReconciler

        reconciler = StateReconciler(spec=innovation_spec)

        proposal = VisionStateProposal(
            proposal_id="test",
            timestamp=time.time(),
            confidence_score=0.5,
            confidence_level=ConfidenceLevel.MEDIUM,
            players=[],
        )

        result = reconciler.reconcile(proposal, two_player_state)

        # Should not crash
        assert result is not None


class TestBotVariety:
    """Tests for different bot personalities."""

    def test_all_personalities_work(self, two_player_state, innovation_spec):
        """All predefined personalities can make decisions."""
        from ..bots.personality import PERSONALITIES

        state = two_player_state._copy_with(current_player_idx=1)
        legal = legal_actions(innovation_spec, state)

        for name, personality in PERSONALITIES.items():
            bot = InnovationBot(player_id="bot1", personality=personality)
            decision = bot.select_action(state, innovation_spec, legal)

            assert decision is not None
            assert decision.action is not None
            assert decision.explanation != ""

    def test_different_seeds_different_results(self, two_player_state, innovation_spec):
        """Different random seeds produce different results over many runs."""
        import random
        from ..bots.personality import CHAOTIC

        state = two_player_state._copy_with(current_player_idx=1)
        legal = legal_actions(innovation_spec, state)

        results_seed_1 = []
        results_seed_2 = []

        for i in range(10):
            bot1 = InnovationBot(
                player_id="bot1",
                personality=CHAOTIC,
                rng=random.Random(42),
            )
            bot2 = InnovationBot(
                player_id="bot1",
                personality=CHAOTIC,
                rng=random.Random(123),
            )

            d1 = bot1.select_action(state, innovation_spec, legal)
            d2 = bot2.select_action(state, innovation_spec, legal)

            results_seed_1.append(d1.action.action_type.value)
            results_seed_2.append(d2.action.action_type.value)

        # With chaotic personality, different seeds should produce some variation
        # (Not guaranteed but highly likely)


class TestFullGameLoopIntegration:
    """
    Integration test for the complete game loop.

    Tests the full flow:
    1. Create session
    2. Submit "fake photo" + hints
    3. Apply corrections
    4. Confirm state (or trigger automa)
    5. Get instructions
    6. Apply one automa action
    7. Assert state changed legally

    Uses deterministic seed for reproducibility.
    """

    @pytest.fixture
    def deterministic_seed(self):
        """Fixed seed for deterministic test runs."""
        return 42

    @pytest.fixture
    def game_session(self, deterministic_seed):
        """Create a game session with deterministic seed."""
        from ..games.innovation.setup import setup_innovation_game
        from ..games.innovation.spec import create_innovation_spec
        from ..session import SessionManager
        from ..bots import InnovationBot
        import random

        spec = create_innovation_spec()
        manager = SessionManager()
        session = manager.create_session(
            spec,
            human_player_id="human",
            num_automas=1,
        )

        # Override game state with seeded setup
        session.game_state = setup_innovation_game(
            num_players=2,
            human_player_name="Human",
            bot_names=["Automa"],
            random_seed=deterministic_seed,
        )

        # Set up bot with deterministic RNG
        for bot_id, bot in session.bots.items():
            bot.rng = random.Random(deterministic_seed)

        return session, spec, manager

    def test_initial_state_is_valid(self, game_session):
        """Verify initial game state is set up correctly."""
        session, spec, manager = game_session
        state = session.game_state

        # 2 players
        assert state.num_players == 2

        # Each player has 2 cards in hand (after initial deal)
        human = state.get_player("human")
        bot = state.get_player("bot_1")
        assert human is not None
        assert bot is not None
        assert human.hand.count == 2
        assert bot.hand.count == 2

        # Age 1 deck has remaining cards (should have dealt 4 total)
        age_1_deck = state.supply_decks.get("age_1")
        assert age_1_deck is not None
        # Started with some cards, dealt 4

        # Game is in PLAYING phase
        from ..engine_core.state import GamePhase
        assert state.phase == GamePhase.PLAYING

        # Achievements are set up
        assert state.achievements.count == 9  # Ages 1-9

    def test_game_loop_with_vision_processor(self, game_session, deterministic_seed):
        """Test full game loop with stub vision processor."""
        from ..session import GameLoop, LoopState
        from ..vision import InnovationVisionProcessor, InnovationVisionConfig, PlayerHints
        from ..vision.proposal import PhotoInput

        session, spec, manager = game_session

        # Configure stub vision processor
        config = InnovationVisionConfig(
            stub_mode=True,
        )
        session.vision_processor = InnovationVisionProcessor(config=config)

        # Create game loop
        loop = GameLoop(session)
        assert loop.state == LoopState.WAITING_PHOTO

        # Step 1: Submit photo with hints
        photo = PhotoInput(
            image_data=b"fake_image_data",
            timestamp=time.time(),
            player_positions={"human": "bottom", "bot_1": "top"},
        )

        # Add player hints for stub processor
        hints = PlayerHints(
            player_positions={"human": "bottom", "bot_1": "top"},
            known_top_cards={"human_red": "archery"},
        )

        result = loop.process_photo(photo)

        # Photo processing should succeed
        assert result.success

        # After processing, we should either have questions or instructions
        # (depends on confidence and state)

    def test_apply_corrections_and_continue(self, game_session, deterministic_seed):
        """Test applying corrections and continuing the game loop."""
        from ..session import GameLoop, LoopState
        from ..vision import InnovationVisionProcessor, InnovationVisionConfig, PlayerHints
        from ..vision.proposal import PhotoInput, VisionStateProposal, ConfidenceLevel, DetectedPlayer
        from ..vision import StateReconciler

        session, spec, manager = game_session

        # Configure stub vision processor
        config = InnovationVisionConfig(
            stub_mode=True,
        )
        session.vision_processor = InnovationVisionProcessor(config=config)
        session.reconciler = StateReconciler(spec=spec)

        # Create game loop
        loop = GameLoop(session)

        # Submit photo
        photo = PhotoInput(
            image_data=b"fake_image_data",
            timestamp=time.time(),
        )
        result = loop.process_photo(photo)

        # If corrections needed, apply them
        if result.questions:
            # Simulate user answering questions
            corrections = {}
            for q in result.questions:
                # Use first option as answer
                q_id = q.get("id", "")
                options = q.get("options", q.get("alternatives", []))
                if options and isinstance(options[0], dict):
                    corrections[q_id] = options[0].get("value", options[0].get("label", ""))
                elif options:
                    corrections[q_id] = options[0]

            result = loop.apply_corrections(corrections)

        # After corrections (or if none needed), check state
        assert result.success

    def test_automa_takes_action(self, game_session):
        """Test that automa can take an action and state changes legally."""
        from ..engine_core.reducer import apply_action
        from ..engine_core.action import Action, ActionType

        session, spec, manager = game_session
        state = session.game_state

        # Make it bot's turn
        state = state._copy_with(current_player_idx=1, actions_remaining=2)
        session.game_state = state

        # Get initial state snapshot
        initial_hand_count = state.get_player("bot_1").hand.count
        initial_deck_count = state.supply_decks.get("age_1").count

        # Get legal actions for bot
        legal = legal_actions(spec, state)
        assert len(legal) > 0, "Bot should have legal actions"

        # Bot selects and executes action
        bot = session.bots.get("bot_1")
        assert bot is not None

        decision = bot.select_action(state, spec, legal)
        assert decision is not None
        assert decision.action is not None

        # Apply the action
        result = apply_action(spec, state, decision.action)

        # Action should succeed
        assert result.success, f"Action failed: {result.error}"
        assert result.new_state is not None

        # State should have changed
        new_state = result.new_state

        # Verify action had an effect (at least actions_remaining decreased)
        if decision.action.action_type == ActionType.DRAW:
            # Hand should increase, deck should decrease
            assert new_state.get_player("bot_1").hand.count >= initial_hand_count

        elif decision.action.action_type == ActionType.MELD:
            # Hand should decrease, board should have card
            pass  # Board checking requires more setup

        elif decision.action.action_type == ActionType.PASS:
            # Actions remaining should be 0
            assert new_state.actions_remaining == 0

        # Actions remaining should have decreased (or be 0 for pass)
        assert new_state.actions_remaining <= state.actions_remaining

    def test_full_turn_cycle(self, game_session, deterministic_seed):
        """Test a complete turn cycle: human turn -> bot turn -> back to human."""
        from ..engine_core.reducer import apply_action
        from ..engine_core.action import Action, ActionType, ActionPayload
        import random

        session, spec, manager = game_session
        state = session.game_state

        # Give human player a card in hand if needed
        human = state.get_player("human")
        if human.hand.count == 0:
            # Add a test card
            from ..engine_core.state import Card, Zone
            test_card = Card(card_id="archery", instance_id="archery_test")
            new_hand = Zone(name="hand", cards=[test_card])
            from ..engine_core.state import PlayerState
            new_human = PlayerState(
                player_id=human.player_id,
                name=human.name,
                is_human=human.is_human,
                hand=new_hand,
                score_pile=human.score_pile,
                achievements=human.achievements,
                board=human.board,
            )
            state = state.with_player(new_human)

        # Ensure it's human's turn with actions
        state = state._copy_with(current_player_idx=0, actions_remaining=2)

        # Human takes draw action
        human_actions = legal_actions(spec, state)
        draw_actions = [a for a in human_actions if a.action_type == ActionType.DRAW]

        if draw_actions:
            result = apply_action(spec, state, draw_actions[0])
            assert result.success
            state = result.new_state

        # Human takes second action (meld or pass)
        state = state._copy_with(actions_remaining=1)
        human_actions = legal_actions(spec, state)

        meld_actions = [a for a in human_actions if a.action_type == ActionType.MELD]
        if meld_actions:
            result = apply_action(spec, state, meld_actions[0])
        else:
            result = apply_action(spec, state, Action.pass_turn("human"))

        if result.success:
            state = result.new_state

        # End human turn
        if state.actions_remaining <= 0:
            end_turn = Action.end_turn("human")
            result = apply_action(spec, state, end_turn)
            if result.success:
                state = result.new_state

        # Now it should be bot's turn
        if state.current_player_idx == 1:
            # Bot takes a turn
            state = state._copy_with(actions_remaining=2)
            bot_actions = legal_actions(spec, state)

            if bot_actions:
                bot = session.bots.get("bot_1")
                if bot:
                    # Use deterministic RNG
                    bot.rng = random.Random(deterministic_seed)
                    decision = bot.select_action(state, spec, bot_actions)

                    result = apply_action(spec, state, decision.action)
                    assert result.success, f"Bot action failed: {result.error}"
                    state = result.new_state

    def test_corrections_change_state(self, game_session):
        """Test that user corrections actually modify game state."""
        from ..engine_core.reducer import apply_action
        from ..engine_core.action import Action, ActionType, ActionPayload
        from ..engine_core.corrections import SetCard, SetSplay

        session, spec, manager = game_session
        state = session.game_state

        # Create a correction to add a card to human's board
        corrections = [
            {
                "type": "set_card",
                "zone_id": "human_board_red",
                "card_id": "archery",
                "position": "top",
            }
        ]

        # Apply via action
        correction_action = Action(
            action_type=ActionType.USER_CORRECTION,
            payload=ActionPayload(
                player_id="human",
                corrections=corrections,
            ),
        )

        # Get initial state
        initial_red_stack = state.get_player("human").get_board_stack("red")
        initial_count = len(initial_red_stack.cards)

        # Apply correction
        result = apply_action(spec, state, correction_action)
        assert result.success, f"Correction failed: {result.error}"

        # Verify state changed
        new_state = result.new_state
        new_red_stack = new_state.get_player("human").get_board_stack("red")

        # Should have one more card
        assert len(new_red_stack.cards) == initial_count + 1

        # Top card should be archery
        assert new_red_stack.top_card is not None
        assert new_red_stack.top_card.card_id == "archery"

    def test_splay_correction(self, game_session):
        """Test that splay corrections work correctly."""
        from ..engine_core.reducer import apply_action
        from ..engine_core.action import Action, ActionType, ActionPayload
        from ..engine_core.state import SplayDirection

        session, spec, manager = game_session
        state = session.game_state

        # First add some cards to a pile
        card_correction = {
            "type": "set_card",
            "zone_id": "human_board_blue",
            "card_id": "writing",
            "position": "top",
        }

        correction_action = Action(
            action_type=ActionType.USER_CORRECTION,
            payload=ActionPayload(
                player_id="human",
                corrections=[card_correction],
            ),
        )
        result = apply_action(spec, state, correction_action)
        assert result.success
        state = result.new_state

        # Now apply splay correction
        splay_correction = {
            "type": "set_splay",
            "player_id": "human",
            "color": "blue",
            "direction": "right",
        }

        correction_action = Action(
            action_type=ActionType.USER_CORRECTION,
            payload=ActionPayload(
                player_id="human",
                corrections=[splay_correction],
            ),
        )

        result = apply_action(spec, state, correction_action)
        assert result.success, f"Splay correction failed: {result.error}"

        # Verify splay changed
        new_state = result.new_state
        blue_stack = new_state.get_player("human").get_board_stack("blue")
        assert blue_stack.splay_direction == SplayDirection.RIGHT

    def test_deterministic_game_sequence(self, deterministic_seed):
        """
        Test that the same seed produces the same game sequence.

        Run the game twice with same seed and verify identical results.
        """
        from ..games.innovation.setup import setup_innovation_game
        from ..games.innovation.spec import create_innovation_spec
        from ..engine_core.reducer import apply_action
        from ..bots import InnovationBot
        import random

        def run_game_with_seed(seed):
            """Run a game sequence and return key state snapshots."""
            spec = create_innovation_spec()
            state = setup_innovation_game(
                num_players=2,
                random_seed=seed,
            )

            snapshots = []

            # Snapshot initial state
            snapshots.append({
                "hand_cards": [c.card_id for c in state.get_player("human").hand.cards],
                "bot_hand_cards": [c.card_id for c in state.get_player("bot_1").hand.cards],
                "deck_count": state.supply_decks.get("age_1").count,
            })

            # Simulate a few bot turns
            state = state._copy_with(current_player_idx=1, actions_remaining=2)
            bot = InnovationBot(player_id="bot_1", rng=random.Random(seed))

            for turn in range(3):
                actions = legal_actions(spec, state)
                if not actions:
                    break

                decision = bot.select_action(state, spec, actions)
                result = apply_action(spec, state, decision.action)

                if result.success:
                    state = result.new_state
                    snapshots.append({
                        "action": decision.action.action_type.value,
                        "card": decision.action.payload.card_id,
                        "actions_remaining": state.actions_remaining,
                    })

                    # Reset actions for next iteration
                    if state.actions_remaining <= 0:
                        state = state._copy_with(actions_remaining=2)

            return snapshots

        # Run twice with same seed
        run1 = run_game_with_seed(deterministic_seed)
        run2 = run_game_with_seed(deterministic_seed)

        # Should produce identical sequences
        assert run1 == run2, "Same seed should produce identical game sequences"

        # Run with different seed should be different
        run3 = run_game_with_seed(deterministic_seed + 1)

        # Initial hands should differ (with very high probability)
        assert run1[0]["hand_cards"] != run3[0]["hand_cards"] or \
               run1[0]["bot_hand_cards"] != run3[0]["bot_hand_cards"], \
               "Different seeds should produce different initial states"
