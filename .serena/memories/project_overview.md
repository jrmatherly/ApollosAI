# ApollosAI (OpenHands) - Project Overview

## Purpose
OpenHands is an automated AI software engineer. It provides a platform where AI agents can write code, run commands, browse the web, and interact with development tools to complete software engineering tasks.

## Tech Stack

### Backend
- **Language**: Python 3.12+
- **Framework**: FastAPI + Uvicorn
- **Package Manager**: Poetry (with UV compatibility)
- **Database**: PostgreSQL (asyncpg, pg8000, SQLAlchemy async)
- **Key Libraries**: LiteLLM, OpenAI SDK, Anthropic SDK, Google GenAI, Docker, Kubernetes, Redis, Socket.IO
- **Observability**: OpenTelemetry, LMNR, PostHog (enterprise)

### Frontend
- **Language**: TypeScript
- **Framework**: React 19 + React Router 7 (SSR)
- **UI Library**: HeroUI, Tailwind CSS 4
- **State Management**: Zustand, TanStack Query
- **Build Tool**: Vite 7
- **Testing**: Vitest, Playwright, Testing Library
- **Node Version**: 22.x+

### Enterprise
- **Auth**: Keycloak (enterprise), Entra ID / Azure AD (apollosai)
- **Billing**: Stripe
- **Migrations**: Alembic
- **Integrations**: GitHub, GitLab, Jira, Linear, Slack

## Repository Structure
```
openhands/          # Python backend (core engine)
  ├── agenthub/     # Agent implementations
  ├── controller/   # Agent controller/orchestrator
  ├── core/         # Core abstractions
  ├── events/       # Event system
  ├── llm/          # LLM integrations
  ├── runtime/      # Sandboxed execution environments
  ├── server/       # API server
  ├── storage/      # Data persistence
  ├── mcp/          # Model Context Protocol
  └── utils/        # Utilities
frontend/           # React/TypeScript frontend
  └── src/
      ├── api/      # Data access layer
      ├── hooks/    # React hooks (query/mutation)
      ├── components/ # UI components
      ├── routes/   # Page routes
      └── types/    # TypeScript types
enterprise/         # Enterprise features (separate license)
apollosai/          # ApollosAI enterprise layer (Phase 1/1.5 + Phase 2)
  ├── server/
  │   ├── auth/     # EntraIDUserAuth, JWT, MSAL, RBAC, UserContextInjector
  │   ├── routes/   # auth, orgs, teams, api_keys
  │   ├── middleware/ # DB-backed server-side sessions
  │   ├── config.py, lifespan.py, db_session.py, deps.py, rate_limit.py
  │   └── app_config.py  # V1 AppServerConfig factory
  ├── storage/
  │   ├── models/   # 12 SQLAlchemy models (user, org, team, role, memberships, etc.)
  │   ├── stores/   # SettingsStore, SecretsStore, ConversationStore
  │   ├── services/ # user_service, token_cache, api_key, token_revocation
  │   ├── database.py, encrypt_utils.py
  │   └── __init__.py
  ├── migrations/   # 2 Alembic versions (separate from enterprise)
  └── bootstrap.py  # Sets OPENHANDS_CONFIG_CLS
tests/              # Python tests
  └── unit/         # Unit tests
```
