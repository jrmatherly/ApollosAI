# Architecture Overview

## Control Flow
User -> Server (FastAPI) -> AgentController (loop) -> Agent (step) -> LLM (LiteLLM)
AgentController -> Runtime (execute actions) -> EventStream (central pub-sub)
EventStream -> Memory, Server, State, Storage subscribers

## Backend Modules
- **core/**: Config management (OpenHandsConfig, AgentConfig, LLMConfig, SandboxConfig, etc.)
- **events/**: Event system — 11 action types, 15+ observation types, EventStream pub-sub
- **controller/**: Agent control loop, state machine, stuck detection
- **agenthub/**: 6 agents — CodeActAgent (production), Browsing, VisualBrowsing, ReadOnly, LOC, Dummy
- **llm/**: LLM interface via LiteLLM, LLMRegistry, Metrics, retry/debug mixins
- **runtime/**: Sandboxed execution — Docker, Kubernetes, Local, Remote, CLI
- **memory/**: History condensation — 8+ condenser strategies, PipelineCondenser
- **storage/**: File backends — Local, S3, GCS, InMemory, WebHook
- **mcp/**: Model Context Protocol client/tool integration
- **server/**: V0 FastAPI routes (conversations, files, git, settings, etc.)
- **app_server/**: V1 server using Software Agent SDK

## Frontend Structure
- **api/**: 16 typed API services (conversation, git, settings, billing, etc.)
- **hooks/**: 57 query hooks + 43 mutation hooks via TanStack Query
- **stores/**: 15 Zustand stores (conversation, agent, home, status, etc.)
- **components/**: 28 feature directories + shared + ui
- **routes/**: React Router 7 with nested layouts (home, conversation, settings, etc.)
- **types/**: V0 + V1 type systems with 40+ type guards

## Enterprise
- 8 platform integrations (GitHub, GitLab, Jira, Jira DC, Linear, Slack, Bitbucket, Solvability)
- 74 storage models, 95 Alembic migrations
- 17 API route modules (auth, billing, orgs, integrations, etc.)
- Abstract Manager pattern for integrations

## Key Patterns
- Registry (agents), Pub-Sub (events), Factory (storage/runtime), Strategy (condensers)
- Service Extension (enterprise overrides), Query/Mutation (frontend data)
- Type Guards (event discrimination), Mixin (LLM retry/debug)
