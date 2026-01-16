# Splay - Board Game Automa Engine

A photo-driven board game engine that plays automa opponents by reading the physical table.

## How It Works

1. **Upload rules** → System compiles to GameSpec (cached)
2. **Start game** → Create ephemeral session
3. **Take photo** → Vision detects table state
4. **Bot plays** → Engine runs automa turns
5. **Follow instructions** → Move physical cards as directed
6. **Repeat** → Photo → Bot → Instructions

## Quick Start

```bash
# Install
pip install -e ".[api]"

# Run locally
uvicorn splay.api.app:app --reload

# API docs at
http://localhost:8000/api/docs
```

## Deploy to Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

Or manually:
1. Fork this repo
2. Connect to Render
3. Deploy (uses `render.yaml` + `Dockerfile`)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/sessions` | Create game |
| POST | `/api/v1/sessions/{id}/photo` | Upload photo |
| GET | `/api/v1/sessions/{id}/state` | Get state |
| DELETE | `/api/v1/sessions/{id}` | End game |

See [API.md](API.md) for full documentation.

## Architecture

- **Photo-driven**: Physical table is source of truth
- **Ephemeral sessions**: No database, state reconstructible from photos
- **Cached specs**: Rules compiled once, cached by hash
- **LLM at build-time only**: No AI during gameplay

See [ARCHITECTURE.md](splay/ARCHITECTURE.md) for details.

## Project Structure

```
splay/
├── api/           # REST API for mobile
├── engine_core/   # Game state & actions
├── vision/        # Photo processing
├── bots/          # Automa AI
├── games/         # Game implementations
│   └── innovation/  # MVP game
├── session/       # Session lifecycle
└── rule_compiler/ # Rules → GameSpec
```

## Current Status

**Working:**
- Core engine, action system, state management
- Bot with heuristic evaluation + personalities
- API layer with WebSocket support
- Session lifecycle

**Stubbed (needs implementation):**
- Vision CV/ML detection
- LLM rule compilation
- Full Innovation card set

See [STUBS.md](splay/STUBS.md) for details.

## License

MIT
