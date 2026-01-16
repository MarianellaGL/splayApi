# Splay Engine API - Mobile Integration Guide

This document defines the API contract for mobile app integration.

## Overview

The Splay Engine exposes a REST API + WebSocket for real-time gameplay.

**Base URL:** `http://<host>:8000/api/v1`

**Authentication:** None required (session-based)

**Content-Type:** `application/json` (except photo uploads: `multipart/form-data`)

## Quick Start

```bash
# Install and run
pip install splay[api]
uvicorn splay.api.app:app --host 0.0.0.0 --port 8000

# API docs available at
http://localhost:8000/api/docs
```

## Game Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     MOBILE APP FLOW                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. POST /sessions                                          │
│     └─→ Create game session                                 │
│                                                             │
│  2. WS /sessions/{id}/ws                                    │
│     └─→ Connect for real-time updates                       │
│                                                             │
│  3. POST /sessions/{id}/photo                               │
│     └─→ Upload photo of table                               │
│         ├─→ If questions: Show correction UI                │
│         │   └─→ POST /sessions/{id}/corrections             │
│         └─→ If OK: Show instructions                        │
│                                                             │
│  4. User executes physical moves                            │
│     └─→ Go to step 3                                        │
│                                                             │
│  5. DELETE /sessions/{id}                                   │
│     └─→ End game                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Endpoints

### Create Session

**POST** `/sessions`

Create a new game session for Innovation.

**Request (form-data):**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `game_type` | string | No | `"innovation"` (default) |
| `num_automas` | int | No | Number of AI players (1-3), default: 1 |
| `human_player_name` | string | No | Display name, default: "Player" |

**Response:**
```json
{
  "session_id": "uuid-string",
  "status": "created",
  "game_name": "Innovation (Base Game)",
  "players": [
    {
      "player_id": "human",
      "name": "Player",
      "is_human": true,
      "is_current_turn": true,
      "score": 0,
      "achievement_count": 0
    },
    {
      "player_id": "bot_1",
      "name": "Automa bot_1",
      "is_human": false,
      "is_current_turn": false,
      "score": 0,
      "achievement_count": 0
    }
  ],
  "current_turn_player_id": "human",
  "turn_number": 0,
  "created_at": 1705420800.0,
  "api_version": "v1"
}
```

---

### Get Session

**GET** `/sessions/{session_id}`

Get session status and basic info.

**Response:** Same as Create Session

---

### Upload Photo

**POST** `/sessions/{session_id}/photo`

Upload a photo of the game table for state detection.

**Request (multipart/form-data):**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `photo` | file | Yes | Image file (JPG, PNG) |
| `player_hints` | string | No | JSON object mapping player_id to position |

**Example player_hints:**
```json
{"human": "bottom", "bot_1": "top"}
```

**Response (success, no questions):**
```json
{
  "session_id": "...",
  "success": true,
  "status": "your_turn",
  "confidence": 0.85,
  "detected_changes": ["red pile top card changed"],
  "questions": [],
  "automa_actions": ["Bot 1: draw", "Bot 1: meld"],
  "instructions": [
    {
      "instruction_id": "inst_0",
      "text": "Bot 1: Draw the top card from Age 1 deck"
    },
    {
      "instruction_id": "inst_1",
      "text": "Place it in Bot 1's hand area"
    }
  ],
  "game_state": { ... },
  "api_version": "v1"
}
```

**Response (needs corrections):**
```json
{
  "session_id": "...",
  "success": true,
  "status": "waiting_correction",
  "confidence": 0.45,
  "questions": [
    {
      "question_id": "human_board_red_top",
      "question_type": "card_identity",
      "question_text": "What is the top card of the red pile?",
      "options": [
        {"card_id": "archery", "name": "Archery"},
        {"card_id": "metalworking", "name": "Metalworking"}
      ],
      "detected_value": "archery",
      "is_required": true
    }
  ],
  "api_version": "v1"
}
```

---

### Submit Corrections

**POST** `/sessions/{session_id}/corrections`

Submit answers to detection questions.

**Request (form-data):**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `corrections` | string | Yes | JSON object: question_id → answer |

**Example corrections:**
```json
{
  "human_board_red_top": "metalworking",
  "deck_age_1_count": 12
}
```

**Response:** Same as photo upload response

---

### Get Game State

**GET** `/sessions/{session_id}/state`

Get complete current game state.

**Response:**
```json
{
  "session_id": "...",
  "status": "your_turn",
  "turn_number": 5,
  "players": [
    {
      "player_id": "human",
      "name": "Player",
      "is_human": true,
      "is_current_turn": true,
      "score": 12,
      "achievement_count": 1,
      "zones": [
        {
          "zone_id": "human_hand",
          "zone_type": "hand",
          "card_count": 3
        },
        {
          "zone_id": "human_board_red",
          "zone_type": "board_pile",
          "card_count": 2,
          "top_card": {
            "card_id": "archery",
            "name": "Archery",
            "age": 1,
            "color": "red"
          },
          "splay_direction": "none"
        }
      ]
    }
  ],
  "available_achievements": [
    {"card_id": "2", "name": "Age 2", "age": 2}
  ],
  "deck_sizes": {"age_1": 8, "age_2": 10, "age_3": 10},
  "your_achievements": 1,
  "achievements_to_win": 6,
  "api_version": "v1"
}
```

---

### Get Instructions

**GET** `/sessions/{session_id}/instructions`

Get pending instructions for human player.

**Response:**
```json
{
  "session_id": "...",
  "instructions": [
    {
      "instruction_id": "inst_0",
      "text": "Bot 1: Draw the top card from Age 2 deck",
      "action_type": "draw"
    }
  ],
  "next_action": "execute_then_photo",
  "api_version": "v1"
}
```

---

### End Session

**DELETE** `/sessions/{session_id}?reason=user_ended`

End and clean up a game session.

**Response:**
```json
{
  "success": true,
  "session_id": "..."
}
```

---

## WebSocket

**WS** `/sessions/{session_id}/ws`

Real-time updates for game state changes.

### Server → Client Messages

**state_update** - Game state changed
```json
{
  "type": "state_update",
  "payload": { /* GameStateResponse */ }
}
```

**instructions** - New instructions for human
```json
{
  "type": "instructions",
  "payload": {
    "instructions": [...]
  }
}
```

**automa_thinking** - Bot is processing
```json
{
  "type": "automa_thinking",
  "payload": {
    "player_id": "bot_1"
  }
}
```

**game_over** - Game ended
```json
{
  "type": "game_over",
  "payload": {
    "winner": "human",
    "reason": "achievements"
  }
}
```

### Client → Server Messages

**ping** - Keep-alive
```json
{"type": "ping"}
```

---

## Status Values

| Status | Description | Next Action |
|--------|-------------|-------------|
| `created` | Session created, awaiting first photo | Take photo |
| `active` | Processing | Wait |
| `waiting_photo` | Ready for next photo | Take photo |
| `waiting_correction` | Questions need answers | Submit corrections |
| `automa_thinking` | Bot is deciding | Wait |
| `your_turn` | Human's turn | Execute instructions, take photo |
| `game_over` | Game ended | End session |

---

## Error Responses

All errors return:
```json
{
  "error": "Human readable message",
  "error_code": "MACHINE_READABLE_CODE",
  "details": { /* optional */ },
  "api_version": "v1"
}
```

| Code | HTTP | Description |
|------|------|-------------|
| `SESSION_NOT_FOUND` | 404 | Session doesn't exist |
| `INVALID_JSON` | 400 | Malformed JSON in request |
| `PHOTO_REQUIRED` | 400 | Photo file missing |
| `GAME_TYPE_UNKNOWN` | 400 | Unknown game type |

---

## Mobile Implementation Notes

### Photo Requirements
- Minimum resolution: 1280x720
- Format: JPEG or PNG
- Lighting: Even, avoid shadows
- Angle: Top-down preferred
- Contents: Entire play area visible

### Correction UI
When `status` is `waiting_correction`:
1. Display each question from `questions` array
2. Show detected_value as pre-selected option
3. Let user confirm or change
4. Submit all answers together

### Instruction Display
Instructions should be displayed clearly:
- One instruction at a time
- Visual indicator for card references
- "Done" button after user executes
- Then prompt for next photo

### Offline Handling
- Session state is server-side only
- No offline play supported in MVP
- If disconnected, take new photo to resync

### Two Photos Per Turn
For complex board changes:
1. Photo after human moves (verifies correctness)
2. Photo after bot instructions executed

---

## Example: Complete Game Flow

```python
import httpx

base = "http://localhost:8000/api/v1"

# 1. Create session
r = httpx.post(f"{base}/sessions", data={"game_type": "innovation"})
session = r.json()
session_id = session["session_id"]

# 2. Take photo and upload
with open("table_photo.jpg", "rb") as f:
    r = httpx.post(
        f"{base}/sessions/{session_id}/photo",
        files={"photo": f}
    )
result = r.json()

# 3. Handle questions if any
if result["questions"]:
    corrections = {}
    for q in result["questions"]:
        # In real app: show UI, get user input
        corrections[q["question_id"]] = q["detected_value"]

    r = httpx.post(
        f"{base}/sessions/{session_id}/corrections",
        data={"corrections": json.dumps(corrections)}
    )
    result = r.json()

# 4. Display instructions
for inst in result["instructions"]:
    print(inst["text"])

# 5. Repeat until game_over
```
