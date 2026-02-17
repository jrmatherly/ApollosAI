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
- CI runs `pre-commit --all-files` — catches entire repo, not just your changed files. Always run `--all-files` locally before pushing.
- CI workflows (`py-tests`, `lint`, `ghcr-build`, `check-package-versions`) skip on docs-only changes (`**/*.md`, `docs/**`, `.scratchpad/**`, `.claude/**`, etc.)
- **ALWAYS run `poetry lock` after ANY `pyproject.toml` change** — including metadata-only edits (name, description, authors, URLs). CI runs `poetry install` which fails if the lock hash is stale.
- `pyproject-fmt` hook can reformat `pyproject.toml` enough to invalidate `poetry.lock` — run `poetry check --lock` after pre-commit and `poetry lock` if it fails.
- Verify lock sync on the BRANCH BEING PUSHED, not just main — feature branches can have stale locks even when main is fine
- Poetry 2.x: `poetry lock --no-update` does NOT exist. Always use `poetry lock` (full resolve).
- Alembic auto-generated migrations always fail ruff — run `pre-commit --all-files` immediately after `alembic revision --autogenerate`, then re-stage the fixed files

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

# ApollosAI enterprise layer
poetry run pytest tests/unit/apollosai/ -v

# Frontend
cd frontend && npm run test                    # vitest
cd frontend && npm run test -- -t "TestName"   # specific test
# Frontend tests: use renderWithProviders() for components needing Redux/providers; query by role/label, not CSS selectors; mock API with MSW handlers
# WebSocket tests (MSW): send events synchronously from connection handler (not setTimeout or captured client refs); use `{ timeout: 5000 }` on waitFor — default 1000ms times out in CI

# Enterprise
PYTHONPATH=".:$PYTHONPATH" poetry run --project=enterprise pytest --forked -n auto -s ./enterprise/tests/unit --cov=enterprise
cd enterprise && PYTHONPATH=".:$PYTHONPATH" poetry run pytest tests/unit/module/ --confcutdir=tests/unit/module  # specific module
```

**Worktree setup for backend testing:**
- `mise` auto-creates a fresh `.venv` in new worktrees — run `poetry install` before any tests
- `from openhands.server.listen import app` requires `frontend/build/` — create `mkdir -p frontend/build && touch frontend/build/index.html` in worktrees
- Always use `poetry run pytest` (not bare `pytest`) to ensure correct venv

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
- Python package is `openhands/` (not `apollos/`) — CI workflows and imports must use `openhands.*` module paths
- Container builds: `containers/build.sh -i openhands` maps to `./containers/app/`; `-i apollosai` maps to `./containers/apollosai/` (enterprise image)

**Frontend**:
- `npm run dev:mock` / `npm run dev:mock:saas` — develop with MSW-mocked backend
- Requires Node.js >=22.12.0
- ESLint 9 flat config (`eslint.config.js`) + Prettier. ESLint 9 is pinned — do NOT upgrade to 10 (plugin incompatibility)
- In worktrees: use `npm run lint` or `./node_modules/.bin/eslint`, never bare `npx eslint` (resolves to v10)
- All user-facing strings must be internationalized (`npm run make-i18n` after adding keys)
- Settings patterns: entity-based (immediate save for MCP/keys) vs form-based (manual save for LLM/app config)

**Git**:
- Use `git add <specific-file>` — never `git add .`
- Pre-commit hooks must pass before pushing
- Always install hooks first: `make install-pre-commit-hooks`
- PR titles use conventional commits: `feat(scope):`, `fix:`, `refactor:`, `docs:`, `test:`, `perf:`, `chore:`
- Worktrees go in `.worktrees/` (gitignored). Use `git worktree add .worktrees/<name> -b <branch>`
- `gh pr merge` must run from the main repo directory, NOT from a worktree (fails with `'main' is already used by worktree`)
- Worktree cleanup order: `git worktree remove <path>` FIRST, then `git branch -d <branch>` — `gh pr merge --delete-branch` can't delete a branch held by a worktree

**Dependency upgrades:**
- `pyproject.toml` has TWO dep sections that must stay in sync: `[project].dependencies` (PEP 621) and `[tool.poetry.dependencies]` (Poetry)
- Scoped `poetry update <pkg1> <pkg2>` is faster and more bisectable than unscoped `poetry update` (571 packages / 14k line lockfile)
- `pip-audit` may not work in mise/uv-managed venvs — set `PIPAPI_PYTHON_LOCATION` to venv python path

## V0/V1 Transition

The V0 backend is deprecated (removal April 2026). V1 uses the Software Agent SDK. The frontend supports both via `settings?.v1_enabled` feature flag. Both `ConversationService` (V0) and `V1ConversationService` coexist.

**V1 Key Types:**
- `UserInfo` extends `Settings` (29 fields) — use `UserInfo(id=user_id, **settings.model_dump(context={'expose_secrets': True}))`, NOT `UserInfo(user_id=...)`
- `SecretSource` is an ABC (abstract `get_value`) — use `StaticSecret(value=..., description=...)` from `openhands.sdk.secret`
- `AuthUserContext` (`openhands/app_server/user/auth_user_context.py`) is the reference V0→V1 bridge pattern
- `UserContextInjector` caches via `InjectorState` attribute (`user_context`); see `Injector` base at `openhands/app_server/services/injector.py`
- `OssAppLifespanService.run_alembic_on_startup` is a field — override it to `False` to skip OpenHands migrations (no need to override `__aenter__`)

## ApollosAI Enterprise Auth Patterns

**Security rules** (from Phase 1.5 review):
- JWT validation failure = hard error. NEVER fall through from invalid-token to unauthenticated access
- `APOLLOSAI_ALLOW_UNAUTHENTICATED` must parse explicitly: `.lower() in ('1', 'true', 'yes')` — Python truthy catches `'false'`/`'0'`
- JWT_SECRET minimum 32 characters enforced at runtime. Separate `SESSION_SECRET` for Starlette SessionMiddleware
- JWT tokens must include `aud: 'apollosai'` claim and validate on decode
- Add `InvalidTokenError` to `apollosai/server/auth/auth_error.py` hierarchy
- When converting module-level constants to getters: remove old constants AND add regression test verifying removal

**Testing rules**:
- Use `monkeypatch.setattr('time.time', ...)` for JWT expiry tests, not `time.sleep()`
- Use specific `jwt.ExpiredSignatureError`/`jwt.InvalidSignatureError`, never `pytest.raises(Exception)`
- Auth route tests must use `FastAPI TestClient`, not just check path existence
- UserContextInjector subclasses must have async `inject()` tests, not just `issubclass`/`hasattr`
- `asyncio_mode = "auto"` in `pyproject.toml` for pytest-asyncio
- Custom pytest marks must be registered in `pytest.ini` under `[pytest] markers =` to avoid `PytestUnknownMarkWarning` in CI
- Test helper classes starting with `Test` need `__test__ = False` to prevent `PytestCollectionWarning`

## Known Issues

(none currently)
