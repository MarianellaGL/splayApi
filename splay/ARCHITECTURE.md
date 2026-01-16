# Splay Engine Architecture

## Core Principles (Non-Negotiable)

### 1. Photo-Driven State
```
The engine does NOT own game state.
The physical table is the source of truth.
Photos are the primary input.
```

**What this means:**
- The engine reconstructs state from each photo
- If we can't see it, we don't know it
- Automas never draw from hidden digital decks
- State is always reconstructible from a new photo

### 2. Ephemeral Sessions
```
Sessions exist only in memory.
When a session ends, all state is deleted.
There is no database for gameplay.
```

**What persists:**
- Compiled GameSpecs (cached by rules hash)

**What does NOT persist:**
- Game state
- Turn history
- Player hands (unless declared)
- Session metadata

### 3. Build-Time Compilation
```
Rules → (LLM) → GameSpec → (Cached)
```

**LLM is used:**
- At build-time to compile rules
- To generate tests
- To validate extraction

**LLM is NOT used:**
- At runtime for gameplay decisions
- To interpret ambiguous states
- To make automa choices

---

## Game Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GAME LIFECYCLE                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐                                                   │
│  │ Rules Text   │ ─── User uploads/pastes rules                     │
│  └──────┬───────┘                                                   │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────┐     ┌─────────────┐                               │
│  │ LLM Compiler │ ──▶ │  GameSpec   │ ─── Cached by rules hash      │
│  └──────────────┘     └──────┬──────┘                               │
│                              │                                       │
│         ┌────────────────────┘                                       │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────┐                                                   │
│  │ New Session  │ ─── Ephemeral, in-memory only                     │
│  └──────┬───────┘                                                   │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │                    GAME LOOP                              │       │
│  │                                                           │       │
│  │   ┌─────────────┐                                        │       │
│  │   │ Take Photo  │ ◀──────────────────────────────┐       │       │
│  │   └──────┬──────┘                                │       │       │
│  │          │                                       │       │       │
│  │          ▼                                       │       │       │
│  │   ┌─────────────┐     ┌─────────────┐           │       │       │
│  │   │   Vision    │ ──▶ │  Proposal   │           │       │       │
│  │   └─────────────┘     └──────┬──────┘           │       │       │
│  │                              │                   │       │       │
│  │          ┌───────────────────┼───────────────┐  │       │       │
│  │          │ Uncertain?        │               │  │       │       │
│  │          ▼                   ▼               │  │       │       │
│  │   ┌─────────────┐     ┌─────────────┐       │  │       │       │
│  │   │ User Fixes  │     │  Reconcile  │       │  │       │       │
│  │   └──────┬──────┘     └──────┬──────┘       │  │       │       │
│  │          │                   │               │  │       │       │
│  │          └───────────────────┘               │  │       │       │
│  │                              │                   │       │       │
│  │                              ▼                   │       │       │
│  │                       ┌─────────────┐           │       │       │
│  │                       │   Engine    │           │       │       │
│  │                       │ (Canonical) │           │       │       │
│  │                       └──────┬──────┘           │       │       │
│  │                              │                   │       │       │
│  │                              ▼                   │       │       │
│  │                       ┌─────────────┐           │       │       │
│  │                       │ Automa Turn │           │       │       │
│  │                       └──────┬──────┘           │       │       │
│  │                              │                   │       │       │
│  │                              ▼                   │       │       │
│  │                       ┌─────────────┐           │       │       │
│  │                       │Instructions │ ──────────┘       │       │
│  │                       │ for Human   │                   │       │
│  │                       └─────────────┘                   │       │
│  │                                                          │       │
│  └──────────────────────────────────────────────────────────┘       │
│         │                                                            │
│         │ Game Over                                                  │
│         ▼                                                            │
│  ┌──────────────┐                                                   │
│  │ End Session  │ ─── All state deleted                             │
│  └──────┬───────┘                                                   │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────┐                                                   │
│  │   Options    │                                                   │
│  │  • Replay    │ ─── Reuse cached spec, new session                │
│  │  • New Game  │ ─── New rules, compile, new session               │
│  └──────────────┘                                                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### Vision Layer
**Owns:** Detection from photos
**Does NOT own:** Game state, rules interpretation

```python
# Vision proposes, engine decides
proposal = vision.process(photo)  # Non-authoritative
state = engine.reconcile(proposal)  # Engine is authoritative
```

### Engine Core
**Owns:** Canonical state, rules validation, legal actions
**Does NOT own:** Hidden information not visible in photos

```python
# Engine only knows what it can see
if not visible_in_photo(card):
    raise UnknownCardError("Cannot reference unseen cards")
```

### Session Manager
**Owns:** Session lifecycle, cleanup
**Does NOT own:** Persistent storage

```python
# Sessions are ephemeral
session = manager.create()  # In-memory only
manager.end(session_id)     # All state deleted
```

### Spec Cache
**Owns:** Compiled specs by rules hash
**Does NOT own:** Game state, session data

```python
# Only specs are cached
cache.put(rules_hash, spec)  # Disk cache
cache.get(rules_hash)        # Returns spec or None
```

---

## What the Automa Can/Cannot Do

### ✅ CAN DO
- Select from legal actions based on visible state
- Execute effects that modify visible zones
- Instruct human to move physical cards
- React to state changes detected via photos

### ❌ CANNOT DO
- Draw from a hidden digital deck
- Know cards that aren't visible
- Remember state from previous sessions
- Make decisions based on hidden information

---

## State Reconstruction

The engine must be able to reconstruct state from a photo at any time:

```python
# Any photo should be sufficient to continue
new_photo = user.take_photo()
state = engine.reconstruct(new_photo)
# Game continues from here
```

This means:
1. No hidden state that can't be photographed
2. No history-dependent decisions
3. No accumulated knowledge across photos

---

## Persistence Summary

| What | Stored Where | Lifetime |
|------|--------------|----------|
| Compiled GameSpec | Disk cache | Until cache cleared |
| Rules text hash | Disk cache key | With spec |
| Game state | Memory | Session only |
| Session metadata | Memory | Session only |
| Turn history | Memory | Session only |
| Player decisions | Memory | Session only |

---

## API Flow

```
1. POST /compile          → Upload rules, get spec_id (cached)
2. POST /sessions         → Create session from spec_id
3. POST /sessions/X/photo → Upload photo, get instructions
4. [Repeat step 3]
5. DELETE /sessions/X     → End session, delete all state
6. [Go to step 2 to replay, or step 1 for new game]
```
