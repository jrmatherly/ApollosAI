# Frontend Development Guide

## Tech Stack
- Remix SPA Mode (React 19 + Vite 7 + React Router 7)
- TypeScript, Redux (legacy) + Zustand + TanStack Query
- Tailwind CSS 4, i18next, HeroUI
- Testing: Vitest, React Testing Library, MSW (Mock Service Worker)
- Node.js >= 22.12.x

## Project Structure
```
frontend/
├── __tests__/          # All tests (organized by component/feature)
├── src/
│   ├── api/            # 16 typed Axios API service classes
│   ├── components/
│   │   ├── features/   # Domain-specific (chat, settings, home, sidebar)
│   │   ├── layout/     # Layout components
│   │   ├── modals/     # Modal dialogs
│   │   └── ui/         # Shared UI components
│   ├── context/        # React context providers
│   ├── hooks/          # Custom hooks (query/, mutation/)
│   ├── i18n/           # Internationalization (translation.json)
│   ├── mocks/          # MSW mocks for dev/test
│   ├── routes/         # React Router file-based routes
│   ├── services/       # Business logic services
│   ├── state/          # Redux state (legacy)
│   ├── stores/         # 15 Zustand stores
│   ├── types/          # TypeScript types (V0 + V1)
│   ├── utils/          # Utility functions
│   └── root.tsx        # Entry point
└── .env.sample         # Environment variable template
```

## Environment Variables
| Variable | Purpose | Default |
|---|---|---|
| VITE_BACKEND_BASE_URL | Backend hostname (WebSocket) | localhost:3000 |
| VITE_BACKEND_HOST | Backend host:port (API) | 127.0.0.1:3000 |
| VITE_MOCK_API | Enable MSW mocking | false |
| VITE_MOCK_SAAS | Simulate SaaS mode | false |
| VITE_USE_TLS | HTTPS/WSS connections | false |
| VITE_FRONTEND_PORT | Frontend port | 3001 |

## Development Commands
- `npm run dev` — dev mode with MSW mocking
- `npm run dev:mock` / `npm run dev:mock:saas` — explicit mock modes
- `npm run test` — run all tests
- `npm run test:coverage` — tests with V8 coverage
- `npm run lint:fix` — ESLint fix
- `npm run build` — production build
- `npm run make-i18n` — regenerate i18n keys

## Testing Patterns
- Use `renderWithProviders()` for components needing Redux/providers
- Use `render()` from RTL for simpler components
- Query by role/label/testID, not CSS selectors
- Mock API with MSW handlers (not manual fetch mocks)
- Use `userEvent.setup()` for realistic interaction simulation
- Use `vi.fn()` for callbacks, verify with `.toHaveBeenCalledWith()`
- Test i18n: verify translation keys render correctly

## Data Flow Pattern
Component → TanStack Query hook → API service → Axios → Backend
- Components NEVER call API services directly
- Query hooks: `use[Resource]` (e.g., useSettings)
- Mutation hooks: `use[Action]` (e.g., useCreateConversation)

## Real-time
- Socket.IO WebSocket connections
- ConversationSubscriptionsProvider for multi-conversation subs
- WebSocket tests (MSW): send events synchronously from connection handler, use `{ timeout: 5000 }` on `waitFor`

## ApollosAI Enterprise Frontend (Phase 2)
- **Login**: `src/utils/generate-entra-auth-url.ts` — Entra ID OAuth2 redirect URL builder
- **Org/Team selectors**: `src/components/features/workspace/org-selector.tsx`, `team-selector.tsx`
- **API service**: `src/api/org-service/org-service.api.ts` — organization/team CRUD
- **Query hooks**: `src/hooks/query/use-organizations.ts`, `use-teams.ts`
- **Mutation hooks**: `src/hooks/mutation/use-switch-org.ts`, `use-switch-team.ts`
- **ESLint**: ESLint 9 flat config (`eslint.config.js`) — pinned to v9, do NOT upgrade to 10 (plugin incompatibility). In worktrees: use `npm run lint` or `./node_modules/.bin/eslint`, never bare `npx eslint`
