# Contributing & Development Workflow

## Development Environment Requirements
- Linux, macOS, or WSL (Ubuntu >= 22.04)
- Docker (macOS: allow default Docker socket in advanced settings)
- Python 3.12 (exact), NodeJS >= 22.x, Poetry >= 1.8
- Ubuntu extras: `build-essential python3.12-dev`; WSL: `netcat`
- Dev container available for VS Code via `.devcontainer/`
- Alternative: use conda/mamba if no sudo access

## Core Make Commands
- `make build` — full build (backend + frontend + pre-commit hooks)
- `make run` — run both servers (backend :3000, frontend :3001)
- `make start-backend` / `make start-frontend` — individual servers
- `make setup-config` — interactive LLM config setup
- `make docker-dev` — develop inside Docker container
- `make docker-run` — run without local tool installation
- `make help` — list all available targets

## Self-hosted Development (OpenHands on OpenHands)
```bash
export INSTALL_DOCKER=0
export RUNTIME=local
make build && make run
```
- Local dev: http://localhost:3001
- External access: `make run FRONTEND_PORT=12000 FRONTEND_HOST=0.0.0.0 BACKEND_HOST=0.0.0.0`

## LLM Debugging
- `export DEBUG=1` and restart backend
- Logs in `logs/llm/CURRENT_DATE/`

## Config Precedence
Environment variables > config.toml > defaults

## Dependency Management
1. Add to `pyproject.toml` or `poetry add xxx`
2. Lock: `poetry lock` (Poetry 2.x: `--no-update` does NOT exist)
3. `pyproject.toml` has TWO dep sections that must stay in sync: `[project].dependencies` (PEP 621) and `[tool.poetry.dependencies]` (Poetry)

## Pre-built Docker Image
- `export SANDBOX_RUNTIME_CONTAINER_IMAGE=ghcr.io/openhands/runtime:1.2-nikolaik`

## PR Convention (Conventional Commits)
Prefixes: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`
- Scoped: `feat(frontend): add dark mode toggle`
- User-facing changes need changelog-friendly description

## Contribution Areas
- **UI/UX**: Small fixes → direct PR; big changes → open issue first or #dev-ui-ux Slack
- **Core Agent**: CodeAct agent prompts at `openhands/agenthub/codeact_agent/`. Changes evaluated on accuracy, efficiency, code complexity. May need SWE-bench evaluation (#evaluation Slack)
- **New Agents**: Add to `openhands/agenthub/`
- **New Runtimes**: Implement interface at `openhands/runtime/base.py`
- **Testing**: `tests/unit/`, `tests/runtime/`, `tests/e2e/`

## Evaluation
- SWE-bench benchmark for agent changes
- CI runs on all PRs (pre-commit hooks, tests)
