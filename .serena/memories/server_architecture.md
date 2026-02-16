# Server Architecture

## V0 Server (openhands/server/) — DEPRECATED, removal April 2026
WebSocket-based FastAPI server for agent task execution.

### Components
1. **listen.py** — Main FastAPI app, CORS, WebSocket handling, API endpoints, static file serving
2. **session/session.py** — WebSocket session management, event dispatch between client and agent
3. **session/agent_session.py** — Agent lifecycle (runtime, controller, security analyzer, event stream)
4. **conversation_manager.py** — Multi-session management, routing, cleanup of inactive sessions

### Server Lifecycle
1. FastAPI init → CORS + static files → ConversationManager init
2. Client connects via WebSocket → Session created/restarted
3. Client sends init request → Agent + Runtime + Controller configured
4. Session manages EventStream bidirectionally (client ↔ agent)
5. ConversationManager periodically cleans inactive sessions

### WebSocket API Schema

#### Actions (client → server)
- `initialize` — {model, directory, agent_cls}
- `start` — {task}
- `read` — {path}
- `write` — {path, content}
- `run` — {command}
- `browse` — {url}
- `think` — {thought}
- `finish` — task complete signal

#### Observations (server → client)
- `read` — {path} + file content
- `browse` — {url} + HTML content
- `run` — {command, exit_code} + output
- `chat` — user message

### Server Environment Variables
- `LLM_API_KEY` — API key (e.g., Anthropic)
- `LLM_MODEL` — Default model (e.g., claude-3-5-sonnet-20241022)
- `SANDBOX_VOLUMES` — Mount paths (host:container:mode)

### Server Start
```bash
uvicorn openhands.server.listen:app --reload --port 3000
```
Test with websocat: `websocat ws://127.0.0.1:3000/ws`

## V1 Server (openhands/app_server/) — NEW ARCHITECTURE
- Uses Software Agent SDK
- Routes at `/api/v1/`
- Feature-flagged via `settings?.v1_enabled`
- Both V0 and V1 coexist during transition
