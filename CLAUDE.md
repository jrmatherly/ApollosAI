# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

OpenHands ("Code Less, Make More") — an automated AI software engineer platform. Python backend + React frontend + enterprise module.

See `AGENTS.md` for detailed procedures (adding LLM models, user settings, frontend actions, enterprise setup).

## Build & Run

```bash
make build                    # Full build (backend + frontend + pre-commit hooks)
make run                      # Run app (backend :3000 + frontend)
make start-backend            # Backend only
make start-frontend           # Frontend only
make setup-config             # Interactive LLM config (model, API key)
make docker-dev               # Develop inside Docker container
make help                     # List all available targets
```

## Lint & Format

**Backend** (must pass before push):
```bash
pre-commit run --config ./dev_config/python/.pre-commit-config.yaml           # Staged files
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml  # All files (matches CI)
```

**Frontend**:
```bash
cd frontend && npm run lint:fix && npm run build
```

**VSCode Extension**:
```bash
cd openhands/integrations/vscode && npm run lint:fix && npm run compile
```

## Testing

```bash
# Backend - single test file
poetry run pytest tests/unit/test_xxx.py

# Backend - full suite with parallelism
poetry run pytest --forked -n auto tests/unit/

# Frontend
cd frontend && npm run test                    # vitest
cd frontend && npm run test -- -t "TestName"   # specific test
# Frontend tests: use renderWithProviders() for components needing Redux/providers; query by role/label, not CSS selectors; mock API with MSW handlers

# Enterprise
PYTHONPATH=".:$PYTHONPATH" poetry run --project=enterprise pytest --forked -n auto -s ./enterprise/tests/unit --cov=enterprise
cd enterprise && PYTHONPATH=".:$PYTHONPATH" poetry run pytest tests/unit/module/ --confcutdir=tests/unit/module  # specific module
```

## Debugging

- `export DEBUG=1` + restart backend — logs LLM prompts/responses to `logs/llm/CURRENT_DATE/`
- Config precedence: environment variables > `config.toml` > defaults
- Self-hosted dev (OpenHands on OpenHands): `INSTALL_DOCKER=0 RUNTIME=local make build && make run`

## Architecture

### Backend (`openhands/`)

The agent loop: **AgentController** calls `Agent.step(state)` which produces an **Action**. The **Runtime** executes it and returns an **Observation**. Everything flows through the **EventStream** (central pub-sub hub).

Key modules:
- `core/config/` — `OpenHandsConfig` composes: AgentConfig, LLMConfig, SandboxConfig, SecurityConfig, MCPConfig, CondenserConfig
- `events/` — 11 Action types (CmdRun, FileRead, FileEdit, Browse, IPython, Message, MCP, etc.) + 15 Observation types. `EventStream` is the pub-sub backbone.
- `controller/` — `AgentController` drives the step loop. `Agent` is the abstract base with a registry pattern (`Agent.register()`, `Agent.get_cls(name)`)
- `agenthub/` — Agent implementations. **CodeActAgent** is the production agent (function calling, bash, editor, browser, IPython, MCP tools). Also: BrowsingAgent, VisualBrowsingAgent, ReadOnlyAgent, LOCAgent, DummyAgent
- `llm/` — `LLM` class wraps LiteLLM for multi-provider access. `LLMRegistry` maps service IDs to instances. RetryMixin + DebugMixin
- `runtime/` — Sandboxed execution: DockerRuntime (production), KubernetesRuntime, LocalRuntime, RemoteRuntime, CLIRuntime
- `memory/condenser/` — History condensation strategies: NoOp, ConversationWindow, Recent, LLMSummarizing, LLMAttention, ObservationMasking, AmortizedForgetting, Pipeline (chainable)
- `storage/` — FileStore interface with backends: Local, S3, GoogleCloud, InMemory, WebHook
- `server/` — V0 FastAPI server (being deprecated)
- `app_server/` — V1 server using Software Agent SDK (new architecture, routes at `/api/v1/`)
- `microagent/` — Loads microagents from `microagents/` (public) and `.openhands/microagents/` (repo-specific). Markdown files with optional frontmatter triggers.

### Frontend (`frontend/src/`)

Data flow: **Component** -> **TanStack Query hook** -> **API service** -> **Axios** -> **Backend**. Components never call API services directly.

- `api/` — 16 typed Axios service classes (conversation, git, settings, billing, auth, events, etc.)
- `hooks/query/` — Query hooks follow `use[Resource]` pattern (e.g., `useSettings`, `useGitRepositories`)
- `hooks/mutation/` — Mutation hooks follow `use[Action]` pattern (e.g., `useCreateConversation`, `useSaveSettings`)
- `stores/` — 15 Zustand stores for client-side state (conversation, agent, home, status, metrics)
- `types/core/` — Event type system with discriminated unions and 40+ type guards. Parallel V0/V1 type systems
- `components/features/` — Feature-based organization: chat (50 files), settings, home, sidebar, browser, terminal
- Real-time via Socket.IO with `ConversationSubscriptionsProvider` for multi-conversation WebSocket subscriptions

### Enterprise (`enterprise/`)

Extends core with auth, billing, and integrations. Licensed under Polyform Free Trial.

- `integrations/` — Abstract `Manager` base class. Implementations: GitHub, GitLab, Jira, Jira DC, Linear, Slack, Bitbucket, Solvability (ML)
- `storage/` — 74 SQLAlchemy store classes for PostgreSQL
- `migrations/` — 92 Alembic versions
- `server/` — 17 route modules (auth, billing, orgs, API keys, webhooks, integration endpoints)
- Uses relative imports without `enterprise.` prefix

## Code Style

**Python**:
- Single quotes for inline strings, double quotes for docstrings (Google convention)
- Modern type hints: `list[X]`, `X | Y`, `X | None` — never `List`, `Union`, `Optional`
- Ruff for linting/formatting (`dev_config/python/ruff.toml`), Mypy for type checking (`dev_config/python/mypy.ini`)
- Ruff and Mypy exclude `third_party/` and `enterprise/` — enterprise has its own lint config at `enterprise/dev_config/`
- `AppMode.OSS` is deprecated — use `AppMode.OPENHANDS`

**Frontend**:
- `npm run dev:mock` / `npm run dev:mock:saas` — develop with MSW-mocked backend
- Requires Node.js >=22.12.0
- ESLint (airbnb-typescript) + Prettier
- All user-facing strings must be internationalized (`npm run make-i18n` after adding keys)
- Settings patterns: entity-based (immediate save for MCP/keys) vs form-based (manual save for LLM/app config)

**Git**:
- Use `git add <specific-file>` — never `git add .`
- Pre-commit hooks must pass before pushing
- Always install hooks first: `make install-pre-commit-hooks`
- PR titles use conventional commits: `feat(scope):`, `fix:`, `refactor:`, `docs:`, `test:`, `perf:`, `chore:`

## V0/V1 Transition

The V0 backend is deprecated (removal April 2026). V1 uses the Software Agent SDK. The frontend supports both via `settings?.v1_enabled` feature flag. Both `ConversationService` (V0) and `V1ConversationService` coexist.

**V1 Key Types:**
- `UserInfo` extends `Settings` (29 fields) — use `UserInfo(id=user_id, **settings.model_dump(context={'expose_secrets': True}))`, NOT `UserInfo(user_id=...)`
- `SecretSource` is an ABC (abstract `get_value`) — use `StaticSecret(value=..., description=...)` from `openhands.sdk.secret`
- `AuthUserContext` (`openhands/app_server/user/auth_user_context.py`) is the reference V0→V1 bridge pattern
- `UserContextInjector` caches via `InjectorState` attribute (`user_context`); see `Injector` base at `openhands/app_server/services/injector.py`
- `OssAppLifespanService.run_alembic_on_startup` is a field — override it to `False` to skip OpenHands migrations (no need to override `__aenter__`)