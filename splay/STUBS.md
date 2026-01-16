# Splay Engine - Stub Documentation

This document lists all intentionally incomplete (stubbed) components
and what needs to be implemented for a production system.

## Legend

- 🔴 **Critical for MVP** - Must be implemented before first playable version
- 🟡 **Important** - Needed for full functionality
- 🟢 **Enhancement** - Nice to have, can be deferred

---

## Vision Layer

### 🔴 InnovationVisionProcessor._detect_players()
**Location:** `splay/vision/processor.py:150`
**Status:** Returns empty list
**Needs:**
- ML model for player area detection
- Card detection within areas
- Position mapping (top/bottom/left/right)

### 🔴 InnovationVisionProcessor._detect_achievements()
**Location:** `splay/vision/processor.py:170`
**Status:** Returns empty list
**Needs:**
- Achievement card recognition
- State extraction

### 🟡 Card recognition by age/color
**Location:** `splay/vision/processor.py`
**Status:** No actual CV implementation
**Needs:**
- Training data (photos of Innovation cards)
- Classification model
- Confidence scoring

### 🟡 Splay direction detection
**Location:** `splay/vision/processor.py`
**Status:** Returns UNKNOWN
**Needs:**
- Card overlap analysis
- Direction classification

---

## State Reconciliation

### 🔴 StateReconciler._build_new_state()
**Location:** `splay/vision/reconciler.py:280`
**Status:** Returns canonical unchanged
**Needs:**
- Merge detected changes into state
- Handle partial updates
- Track what changed

### 🟡 Legal state transition validation
**Location:** `splay/vision/reconciler.py:190`
**Status:** Basic checks only
**Needs:**
- Full rules validation
- Impossible state detection
- Cheating detection

---

## Engine Core

### 🔴 EffectResolver step implementations
**Location:** `splay/engine_core/effect_resolver.py:200-300`
**Status:** Most steps return state unchanged
**Needs per step:**
- `_step_draw`: Full deck management
- `_step_meld`: Board placement logic
- `_step_score`: Score pile management
- `_step_transfer`: Zone-to-zone movement
- `_step_return`: Return to supply
- `_step_demand`: Opponent targeting
- `_step_for_each`: Loop execution

### 🔴 Expression evaluator
**Location:** `splay/engine_core/effect_resolver.py:400`
**Status:** Only handles integers
**Needs:**
- Full expression parser
- State accessors (player.score, card.age, etc.)
- Function calls (count(), has(), sum())
- Condition evaluation

### 🟡 Icon counting with splay
**Location:** `splay/engine_core/effect_resolver.py:380`
**Status:** Returns 0
**Needs:**
- Proper splay visibility rules
- Icon position handling

### 🟡 Choice generation for effects
**Location:** `splay/engine_core/effect_resolver.py:280`
**Status:** Basic card choices only
**Needs:**
- All choice types
- Filter expression evaluation
- Valid option enumeration

---

## Reducer

### 🔴 Reducer._handle_vision_update()
**Location:** `splay/engine_core/reducer.py:200`
**Status:** Returns failure
**Needs:**
- Full reconciliation integration
- State update from vision

### 🔴 Reducer._handle_user_correction()
**Location:** `splay/engine_core/reducer.py:210`
**Status:** Returns failure
**Needs:**
- Apply corrections to state
- Validation

### 🟡 Achievement requirement validation
**Location:** `splay/engine_core/reducer.py:170`
**Status:** Allows all achieves
**Needs:**
- Score threshold check
- Top card age check

---

## Rule Compiler

### 🔴 RuleCompiler._compile_with_llm()
**Location:** `splay/rule_compiler/compiler.py:100`
**Status:** Returns minimal spec
**Needs:**
- LLM client integration
- Prompt execution
- Response parsing
- GameSpec construction

### 🟡 SpecCache serialization
**Location:** `splay/rule_compiler/cache.py:100`
**Status:** Saves metadata only
**Needs:**
- Full GameSpec serialization
- Effect DSL serialization
- Deserialization

### 🟢 Test generation from rules
**Location:** `splay/rule_compiler/prompts.py`
**Status:** Prompt defined, not used
**Needs:**
- LLM test generation
- Test case format
- pytest integration

---

## Innovation Game

### 🔴 Full card definitions
**Location:** `splay/games/innovation/cards.py`
**Status:** 7 cards defined
**Needs:**
- All 105 base game cards
- All dogma effects encoded
- Icon data verified

### 🟡 setup_innovation_game()
**Location:** `splay/games/innovation/state.py:100`
**Status:** Returns unchanged state
**Needs:**
- Deck creation and shuffling
- Achievement setup
- Initial deal
- First meld

### 🟡 Special achievements
**Location:** `splay/games/innovation/state.py`
**Status:** Not implemented
**Needs:**
- 5 special achievement definitions
- Claim condition checking

---

## Session Management

### 🟡 Stale session cleanup
**Location:** `splay/session/manager.py:150`
**Status:** Basic implementation
**Needs:**
- Background cleanup task
- Configurable timeouts
- Graceful shutdown

### 🟢 Session persistence for recovery
**Location:** N/A
**Status:** Not implemented (by design)
**Note:** Sessions are ephemeral. Optional recovery could
save to temp file and restore on crash.

---

## Testing

### 🟡 Integration tests
**Location:** `splay/tests/integration/`
**Status:** Directory created, no tests
**Needs:**
- Full game playthrough tests
- Vision → Engine integration
- Multi-turn scenarios

### 🟡 Property-based tests
**Status:** Not implemented
**Needs:**
- Hypothesis integration
- State invariant properties
- Action legality properties

### 🟢 Performance benchmarks
**Status:** Not implemented
**Needs:**
- Action generation speed
- Effect resolution speed
- Vision processing speed

---

## What's Working Now

The following components are functional and can be used:

1. **Spec Schema** - Complete data structures for game specs
2. **Effect DSL** - Step-based effect representation
3. **State Management** - Game state with zones and stacks
4. **Action System** - Actions, payloads, results
5. **Action Generator** - Legal action enumeration
6. **Basic Reducer** - Draw, meld, achieve (partial)
7. **Bot Policy** - Random, first-legal, heuristic
8. **Heuristic Evaluator** - State scoring
9. **Personalities** - Configurable play styles
10. **Innovation Bot** - 1-ply action selection
11. **Vision Proposal** - Data structures
12. **Reconciliation** - Basic conflict detection
13. **Session Manager** - Session lifecycle
14. **Game Loop** - Photo-driven flow structure

---

## Implementation Priority Order

For a playable MVP:

1. **Vision detection** - Need to read the table
2. **State building from vision** - Need to create state
3. **Effect step execution** - Need dogma to work
4. **Full card set** - Need all Innovation cards
5. **Expression evaluation** - Need conditions to work
6. **LLM compilation** - For other games beyond Innovation

Human decisions still required:
- ML model architecture for vision
- LLM provider selection
- Mobile app framework
- UI/UX design for corrections
