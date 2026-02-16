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
- **Auth**: Keycloak
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
tests/              # Python tests
  └── unit/         # Unit tests
```
