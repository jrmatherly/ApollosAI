# ApollosAI (OpenHands) - Project Index

> Auto-generated project documentation. OpenHands v1.3.0 — an automated AI software engineer platform.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [Repository Structure](#3-repository-structure)
4. [Backend Architecture](#4-backend-architecture)
5. [Frontend Architecture](#5-frontend-architecture)
6. [Enterprise Module](#6-enterprise-module)
7. [Configuration](#7-configuration)
8. [CI/CD & DevOps](#8-cicd--devops)
9. [Testing](#9-testing)
10. [Development Commands](#10-development-commands)
11. [Code Style & Conventions](#11-code-style--conventions)
12. [Key Architectural Patterns](#12-key-architectural-patterns)

---

## 1. Project Overview

**OpenHands** ("Code Less, Make More") is an automated AI software engineer. It provides a platform where AI agents can write code, run commands, browse the web, and interact with development tools to complete software engineering tasks autonomously.

- **License**: MIT (core), Polyform Free Trial (enterprise)
- **Python**: `>=3.12,<3.14`
- **Node**: `>=22.12.0`
- **Default Agent**: CodeActAgent
- **Default LLM**: gpt-4o

> **V0/V1 Transition**: The V0 backend (`openhands/`) is deprecated as of 1.0.0 (removal April 2026). V1 uses the Software Agent SDK via `openhands/app_server/`.

---

## 2. Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend Language** | Python 3.12+ |
| **Backend Framework** | FastAPI + Uvicorn |
| **Package Manager** | Poetry (with UV compatibility) |
| **Database** | PostgreSQL (SQLAlchemy async + AsyncPG) |
| **Cache/Queue** | Redis |
| **LLM Integration** | LiteLLM (OpenAI, Anthropic, Gemini, Bedrock, etc.) |
| **Frontend Language** | TypeScript |
| **Frontend Framework** | React 19 + React Router 7 (SSR) |
| **UI Components** | HeroUI + Tailwind CSS 4 + CVA |
| **Data Fetching** | TanStack Query (React Query) |
| **Client State** | Zustand |
| **Real-time** | Socket.IO |
| **Build Tool** | Vite 7 |
| **Observability** | OpenTelemetry, LMNR, PostHog |
| **Containerization** | Docker (multi-stage), Kubernetes |
| **CI/CD** | GitHub Actions (17 workflows) |

---

## 3. Repository Structure

```
ApollosAI/
├── openhands/                 # Python backend (core engine)
│   ├── agenthub/              # Agent implementations (6 agents)
│   ├── app_server/            # V1 application server (SDK-based)
│   ├── controller/            # Agent control loop & state machine
│   ├── core/                  # Configuration, messages, exceptions
│   ├── events/                # Event system (actions + observations)
│   ├── llm/                   # LLM provider interface (via LiteLLM)
│   ├── memory/                # Conversation history & condensers
│   ├── mcp/                   # Model Context Protocol integration
│   ├── runtime/               # Sandboxed execution (Docker, K8s, local)
│   ├── server/                # FastAPI HTTP server (V0)
│   ├── storage/               # File storage backends (local, S3, GCS)
│   ├── security/              # Security analysis
│   ├── microagent/            # Microagent loading
│   ├── integrations/          # IDE integrations (VSCode extension)
│   └── utils/                 # Shared utilities
├── frontend/                  # React/TypeScript frontend
│   └── src/
│       ├── api/               # Data access layer (16 services)
│       ├── hooks/             # TanStack Query/Mutation hooks (150+)
│       ├── components/        # UI components (28 feature dirs)
│       ├── stores/            # Zustand stores (15 stores)
│       ├── routes/            # Page routes (23 files)
│       ├── types/             # TypeScript types (V0 + V1)
│       ├── ui/                # Design system primitives
│       ├── contexts/          # React contexts (WebSocket, subscriptions)
│       ├── services/          # Non-API services (chat, terminal, state)
│       ├── utils/             # Utilities (50+ modules)
│       └── i18n/              # Internationalization
├── enterprise/                # Enterprise features (separate license)
│   ├── server/                # Enterprise API routes (17 modules)
│   ├── integrations/          # Platform integrations (8 platforms)
│   ├── storage/               # Database models & stores (74 models)
│   ├── migrations/            # Alembic migrations (95 versions)
│   └── tests/                 # Enterprise unit tests
├── tests/                     # Core test suite
│   ├── unit/                  # Unit tests (178 files)
│   ├── e2e/                   # End-to-end tests
│   └── runtime/               # Runtime/sandbox tests
├── containers/                # Docker build files
├── .github/                   # CI/CD workflows (17 workflows)
├── dev_config/                # Linting & type checking config
├── scripts/                   # Build & utility scripts
└── config.template.toml       # Configuration template
```

---

## 4. Backend Architecture

### 4.1 Control Flow

```
User Request
    │
    ▼
┌──────────┐     ┌──────────┐     ┌─────────┐
│  Server   │────▶│Controller│────▶│  Agent   │
│ (FastAPI) │     │  (Loop)  │     │ (Step)   │
└──────────┘     └────┬─────┘     └────┬─────┘
                      │                │
                      │   Actions      │ LLM Calls
                      ▼                ▼
                ┌──────────┐     ┌──────────┐
                │ Runtime   │     │   LLM    │
                │ (Execute) │     │(LiteLLM) │
                └────┬─────┘     └──────────┘
                     │
                     ▼
              ┌────────────┐
              │EventStream │  ◄── Central pub-sub hub
              └────────────┘
                     │
         ┌───────┬───┴───┬────────┐
         ▼       ▼       ▼        ▼
      Memory   Server   State   Storage
```

### 4.2 Core Modules

#### `core/` — Configuration & Base Types
Central configuration management aggregating all subsystem configs.

| Config Class | Purpose |
|-------------|---------|
| `OpenHandsConfig` | Root config (composes all below) |
| `AgentConfig` | Agent capabilities (browsing, editor, jupyter, MCP) |
| `LLMConfig` | Model, provider, tokens, temperature, cost |
| `SandboxConfig` | Runtime type, container image, auto-lint |
| `SecurityConfig` | Security analyzer selection |
| `MCPConfig` | MCP server definitions (stdio, SSE, HTTP) |
| `CondenserConfig` | History condensation strategy |
| `ModelRoutingConfig` | LLM model selection logic |

Key types: `Message` (LLM API format with vision/caching), `TextContent`, `ImageContent`

#### `events/` — Event System
Append-only event log with pub-sub. All agent-environment interaction flows through events.

**Actions** (11 types): `CmdRunAction`, `FileReadAction`, `FileEditAction`, `BrowseURLAction`, `IPythonRunCellAction`, `AgentFinishAction`, `MessageAction`, `TaskTrackingAction`, `MCPAction`, `AgentDelegateAction`, `AgentThinkAction`

**Observations** (15+ types): `CmdOutputObservation`, `FileReadObservation`, `BrowserOutputObservation`, `ErrorObservation`, `AgentStateChangeObservation`, `MCPObservation`, `TaskTrackingObservation`

**Key classes**: `Event` (base), `EventStream` (pub-sub hub), `EventStore` (persistence), `EventSource` enum (AGENT, USER, ENVIRONMENT)

#### `controller/` — Agent Control Loop
Orchestrates the main step loop: Agent produces Actions, Runtime executes them, Observations feed back.

- `Agent` (abstract base): `step(state) -> Action`, registry pattern (`register()`, `get_cls()`, `list_agents()`)
- `AgentController`: Main loop driver, handles stuck detection, history condensation
- `State`: Tracks history, plan, metrics, current step

#### `agenthub/` — Agent Implementations

| Agent | Purpose | Status |
|-------|---------|--------|
| **CodeActAgent** | General-purpose code execution (V2.2) | Production |
| **BrowsingAgent** | Web browsing & information extraction | Active |
| **VisualBrowsingAgent** | Visual browsing with Set-of-Marks | Active |
| **ReadOnlyAgent** | Read-only code analysis (no writes) | Active |
| **LOCAgent** | Lines-of-code analysis | Active |
| **DummyAgent** | Test/demo agent | Testing |

CodeActAgent tools: bash, file editor, browser, IPython, task tracker, finish, think, condensation request

#### `llm/` — Language Model Interface
Unified LLM access via LiteLLM with retry, streaming, and cost tracking.

- `LLM`: Main interface — `completion(messages, tools)`, supports function calling, vision, caching
- `AsyncLLM`, `StreamingLLM`: Async and streaming wrappers
- `LLMRegistry`: Maps service_id to LLM instances
- `Metrics`: Token/cost/latency tracking
- `ModelFeatures`: Capability detection (vision, tool calling, caching)
- Mixins: `RetryMixin`, `DebugMixin`

#### `runtime/` — Sandboxed Execution

| Runtime | Purpose |
|---------|---------|
| `DockerRuntime` | Containerized sandbox (production) |
| `KubernetesRuntime` | K8s pod execution (cloud-native) |
| `LocalRuntime` | Local machine (development) |
| `RemoteRuntime` | Remote server execution |
| `CLIRuntime` | Terminal-only mode |

Features: command execution, file ops, browser automation, git operations, MCP tools, plugin management

#### `memory/` — History Condensation

| Condenser | Strategy |
|-----------|----------|
| `NoOpCondenser` | Keep all events |
| `ConversationWindowCondenser` | Keep recent N events |
| `RecentEventsCondenser` | Keep most recent |
| `LLMSummarizingCondenser` | LLM-based summarization |
| `LLMAttentionCondenser` | Attention-weighted selection |
| `ObservationMaskingCondenser` | Mask redundant observations |
| `AmortizedForgettingCondenser` | Gradual forgetting |
| `PipelineCondenser` | Chain multiple strategies |

#### `storage/` — File Persistence
Backends: `LocalFileStore`, `S3FileStore`, `GoogleCloudFileStore`, `InMemoryFileStore`, `WebHookFileStore`

Interface: `upload()`, `download()`, `list()`, `delete()`, `exists()`

#### `mcp/` — Model Context Protocol
Integration with MCP servers for extended tool availability.
- `MCPClient`: Connect to MCP servers
- `convert_mcp_clients_to_tools()`: Convert to LLM tool format
- `call_tool_mcp()`: Execute MCP tools

#### `server/` — FastAPI HTTP Server (V0)
Routes: conversations, files, git, feedback, MCP, security, settings, secrets, health, trajectory

#### `app_server/` — V1 Application Server
New architecture using Software Agent SDK. Routes: `/api/v1/events`, `/api/v1/conversations`, `/api/v1/sandboxes`, `/api/v1/users`, `/api/v1/webhooks`

---

## 5. Frontend Architecture

### 5.1 Data Flow

```
React Component
    │
    ▼ (uses hook)
TanStack Query/Mutation Hook
    │
    ▼ (calls service)
API Service (typed wrapper)
    │
    ▼ (uses shared instance)
Axios (open-hands-axios.ts)
    │
    ▼
Backend API
```

**Rule**: Components never call API services directly — always through TanStack Query hooks.

### 5.2 Routing (React Router 7)

| Route | Page | Auth |
|-------|------|------|
| `/login` | Login page | Public |
| `/` | Home (repository selection) | Protected |
| `/conversations/:id` | Main conversation UI | Protected |
| `/settings/*` | Settings (8 sub-routes) | Protected |
| `/microagent-management` | Microagent config | Protected |
| `/shared/conversations/:id` | Shared conversation view | Public |
| `/accept-tos` | Terms of service | Protected |
| `/oauth/device/verify` | Device OAuth | Protected |

Settings sub-routes: llm, mcp, user, integrations, app, billing, secrets, api-keys

### 5.3 API Services (16 services)

| Service | Purpose |
|---------|---------|
| `conversation-service` | Core conversation CRUD |
| `v1-conversation-service` | V1 task-based conversations |
| `auth-service` | Authentication (login, logout) |
| `git-service` | Git repos, branches, changes, PRs |
| `settings-service` | User settings read/write |
| `event-service` | Event streaming |
| `user-service` | User data & conversations |
| `integration-service` | External integrations |
| `billing-service` | Stripe billing/subscriptions |
| `sandbox-service` | Sandbox metrics & status |
| `microagent-management-service` | Microagent CRUD |
| `option-service` | LLM/provider options |
| `email-service` | Email verification |
| `suggestions-service` | Task suggestions |
| `shared-conversation-service` | Public conversation access |

### 5.4 Hooks (150+ hooks)

**Query hooks** (57): `use-active-conversation`, `use-git-repositories`, `use-settings`, `use-ai-config-options`, `use-balance`, `use-paginated-conversations`, etc.

**Mutation hooks** (43): `use-create-conversation`, `use-save-settings`, `use-add-mcp-server`, `use-upload-files`, `use-create-billing-session`, etc.

**Naming**: Query = `use[Resource]`, Mutation = `use[Action]`

### 5.5 Zustand Stores (15)

| Store | Key State |
|-------|-----------|
| `conversation-store` | Selected tab, panels, images, files, plan content |
| `agent-store` | Agent state (LOADING, IDLE, RUNNING, ERROR) |
| `home-store` | Recent repositories, last provider (persisted) |
| `event-message-store` | Cached event messages |
| `status-store` | Connection & runtime status |
| `metrics-store` | Cost, token usage |
| `browser-store` | Browser tab state |
| `v1-conversation-state-store` | V1 task polling state |

### 5.6 Type System
- V0 types in `types/core/` with discriminated unions and 40+ type guards
- V1 types in `types/v1/core/` (parallel structure)
- Key types: `OpenHandsBaseEvent`, `OpenHandsActionEvent<T>`, `OpenHandsObservationEvent<T>`, `Settings`, `Conversation`

### 5.7 UI Design System
Minimal library using Tailwind CSS + CVA (Class Variance Authority):
- Components: `Card`, `Typography`, `HelpLink`, `ContextMenu`, `Divider`, `Pre`
- Dark theme: `bg-[#26282D]`, `border-[#727987]`, `text-white`
- External: HeroUI component library

### 5.8 Real-time Communication
- Socket.IO for WebSocket connections
- `ConversationSubscriptionsProvider`: Multi-conversation subscriptions with event buffering
- Automatic reconnection/recovery
- V0/V1 dual support with feature flag (`settings?.v1_enabled`)

---

## 6. Enterprise Module

### 6.1 Overview
Enterprise extends the open-source core with auth, billing, integrations, and multi-tenant features. Licensed under Polyform Free Trial (30-day limit).

### 6.2 Integrations (8 platforms)

| Platform | Manager Class | Features |
|----------|-------------|----------|
| **GitHub** | `GithubManager` | Issue automation, webhooks, PR management, solvability analysis |
| **GitLab** | `GitlabManager` | CI/CD integration, webhook handling |
| **Jira Cloud** | `JiraManager` | Issue resolution, project management |
| **Jira DC** | `JiraDcManager` | Self-hosted Jira integration |
| **Linear** | `LinearManager` | Issue tracking |
| **Slack** | `SlackManager` | Workspace communication, notifications |
| **Bitbucket** | `BitbucketService` | Service extension |
| **Solvability** | ML models | Issue classification, difficulty scoring |

Pattern: Abstract `Manager` base class with async receive/send message flow.

### 6.3 Storage (74 store classes)
Categories: Authentication (API keys, tokens), User management, Integration data, Conversations, Repositories, Billing (Stripe), Secrets (encrypted), Experiments (A/B testing)

### 6.4 Database Migrations
95 Alembic versions covering auth, user data, integrations, conversations, billing, feature flags.

### 6.5 Enterprise Server Routes (17 modules)
Auth, API keys, user, orgs, billing, OAuth device flow, webhooks, GitHub proxy, feedback, debugging, readiness, integration routes (Jira, Linear, Slack), MCP patch.

### 6.6 Authentication Flow
1. GitHub app OAuth -> short-lived token + refresh token
2. Token stored in `GithubTokenManager`
3. Cookie issued with `github_user_id`
4. Requests use cookie ID, tokens fetched server-side

---

## 7. Configuration

### 7.1 Main Config (`config.template.toml`)

| Section | Key Options |
|---------|------------|
| `[core]` | `workspace_base`, `cache_dir`, `debug`, `max_iterations`, `default_agent`, `jwt_secret` |
| `[llm]` | `api_key`, `model`, `temperature`, `max_tokens`, `timeout`, `custom_tokenizer` |
| `[agent]` | `enable_browsing`, `enable_editor`, `enable_jupyter`, `llm_config` |
| `[sandbox]` | `timeout`, `base_container_image`, `runtime_extra_deps`, `enable_gpu` |
| `[security]` | `confirmation_mode`, `security_analyzer` |
| `[condenser]` | `type` (noop, llm, amortized, observation_masking, recent, llm_attention) |
| `[kubernetes]` | `namespace`, `ingress_domain`, `pvc_storage_size` |
| `[mcp]` | `sse_servers`, `shttp_servers`, `stdio_servers` |
| `[model_routing]` | `router_name` (noop_router, multimodal_router) |

### 7.2 Frontend Environment
`VITE_BACKEND_HOST`, `VITE_USE_TLS`, `VITE_INSECURE_SKIP_VERIFY`, `VITE_FRONTEND_PORT`, `VITE_MOCK_API`

---

## 8. CI/CD & DevOps

### 8.1 GitHub Workflows (17)

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `py-tests.yml` | Push/PR | Python unit & runtime tests |
| `lint.yml` | Push/PR | Code linting checks |
| `fe-unit-tests.yml` | Frontend changes | Frontend unit tests |
| `fe-e2e-tests.yml` | Frontend changes | Frontend E2E tests |
| `e2e-tests.yml` | Main/PR | Integration tests |
| `ghcr-build.yml` | Main/tags | Docker image builds to GHCR |
| `enterprise-check-migrations.yml` | PR | Migration sync verification |
| `openhands-resolver.yml` | Issue resolution | Complex resolver orchestration |
| `pr-review-by-openhands.yml` | PRs | AI-powered PR review |
| `pypi-release.yml` | Release | Python package publishing |
| `npm-publish-ui.yml` | Release | UI package to NPM |

### 8.2 Docker

| Image | Base | Purpose |
|-------|------|---------|
| Main app (`containers/app/`) | Python 3.13.7 (multi-stage) | Production deployment |
| Enterprise (`enterprise/`) | `ghcr.io/openhands/openhands:latest` | Enterprise server |
| Dev (`containers/dev/`) | Python 3.13.7 | Development |
| Runtime sandboxes | nikolaik/python-nodejs, ubuntu:24.04 | Agent execution |

**docker-compose.yml**: Single `openhands` service on port 3000, mounts Docker socket + config + workspace.

---

## 9. Testing

### 9.1 Backend (pytest)

```bash
# Unit tests
poetry run pytest tests/unit/test_xxx.py

# Full suite with parallelism
poetry run pytest --forked -n auto tests/unit/

# Enterprise tests
PYTHONPATH=".:$PYTHONPATH" poetry run --project=enterprise pytest --forked -n auto ./enterprise/tests/unit --cov=enterprise
```

Plugins: pytest-asyncio, pytest-cov, pytest-forked, pytest-xdist, pytest-timeout, pytest-reruns

### 9.2 Frontend (vitest + playwright)

```bash
cd frontend
npm run test           # Unit tests (vitest)
npm run test:e2e       # E2E tests (playwright)
npm run test:coverage  # Coverage report
```

### 9.3 Test Organization
- `tests/unit/` — 178 Python test files
- `tests/e2e/` — 11 E2E test directories
- `tests/runtime/` — 21 runtime test directories
- `enterprise/tests/unit/` — 58 enterprise test files

---

## 10. Development Commands

### Quick Reference

```bash
# Full build
make build

# Backend lint (staged files)
pre-commit run --config ./dev_config/python/.pre-commit-config.yaml

# Backend lint (all files, CI-matching)
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml

# Frontend lint + build
cd frontend && npm run lint:fix && npm run build

# Backend tests
poetry run pytest tests/unit/test_xxx.py

# Frontend tests
cd frontend && npm run test

# Run full app
make run FRONTEND_PORT=12000 BACKEND_HOST=0.0.0.0

# Install pre-commit hooks
make install-pre-commit-hooks
```

---

## 11. Code Style & Conventions

### Python
- **Formatter/Linter**: Ruff 0.12.5 + Mypy 1.17
- **Quotes**: Single inline, double docstrings (Google convention)
- **Type Hints**: Modern — `list[X]`, `X | Y`, `X | None` (not `List`, `Union`, `Optional`)
- **Imports**: Ruff isort; enterprise uses relative imports without `enterprise.` prefix
- **Deprecation**: `AppMode.OSS` is deprecated, use `AppMode.OPENHANDS`

### TypeScript/React
- **Linter**: ESLint (airbnb-typescript) + Prettier
- **Architecture**: TanStack Query for all data fetching; never call API from components directly
- **Hooks**: Query = `use[Resource]`, Mutation = `use[Action]`
- **State**: Zustand for client state, TanStack Query for server state
- **i18n**: All user-facing strings must be internationalized

### Git
- Use `git add <specific-file>` (not `git add .`)
- Pre-commit hooks must pass before push
- PR template at `.github/pull_request_template.md`

---

## 12. Key Architectural Patterns

| Pattern | Where | Description |
|---------|-------|-------------|
| **Registry** | `Agent._registry` | Agents self-register; accessed via `get_cls(name)` |
| **Pub-Sub** | `EventStream` | Central event hub for all inter-component communication |
| **Factory** | `get_file_store()`, `get_runtime_cls()` | Runtime/storage backend selection |
| **Strategy** | `Condenser` implementations | Pluggable history condensation |
| **Mixin** | `RetryMixin`, `DebugMixin`, `FileEditRuntimeMixin` | Cross-cutting LLM/runtime concerns |
| **Observer** | `EventStreamSubscriber` | Components subscribe to event types |
| **Service Extension** | `GitHubService -> SaaSGitHubService` | Enterprise overrides core services |
| **Query/Mutation** | TanStack hooks | Declarative data fetching with cache |
| **Store** | Zustand | Minimal client-side state management |
| **Type Guards** | 40+ predicates in `types/core/guards.ts` | Runtime type discrimination for events |

---

*Generated 2026-02-16 | OpenHands v1.3.0 | Python 3.12+ | React 19 | TypeScript*