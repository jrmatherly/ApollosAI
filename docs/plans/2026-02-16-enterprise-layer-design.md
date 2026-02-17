# ApollosAI Enterprise Layer Design

> Date: 2026-02-16
> Status: Validated — Phase 1/1.5 (PR #1) and Phase 2 (PR #5) implemented and merged to main
> Source: `.scratchpad/apollosai_ent_research/` (7 docs, independently verified against codebase)

## Purpose

Build an enterprise layer for ApollosAI on top of the OpenHands platform. This replaces the existing enterprise module (PolyForm-licensed) with a clean-room implementation using Entra ID auth, Org/Team/User RBAC, and PostgreSQL storage.

## Architecture

### Extension Pattern

OpenHands uses dynamic import + class override for extensibility:
- `OPENHANDS_CONFIG_CLS` env var loads a custom `ServerConfig` subclass
- Config attributes point to implementation classes (strings → `get_impl()` dynamic import)
- V1 uses typed DI via concrete `*Injector` subclasses (inheriting from `Injector[T]` + `DiscriminatedUnionMixin`) as fields on `AppServerConfig`
- V0 is deprecated (removal April 2026) — Phase 1 bridges V0 (same approach as enterprise), Phase 1.5 adds V1-native `UserContextInjector`

### Interfaces to Implement

**Phase 1 (skeleton) + Phase 1.5 (wired):**

| Interface | ApollosAI Class | Purpose | When |
|-----------|----------------|---------|------|
| `ServerConfig` | `ApollosAIServerConfig` | V0 config overrides (bridges to V1) | Phase 1 |
| `UserAuth` | `EntraIDUserAuth` | MSAL-based auth (V0 interface) | Phase 1 (skeleton), 1.5 (MSAL) |
| `SettingsStore` | `ApollosAISettingsStore` | Org→Team→User settings resolution | Phase 1 (stub), 2 (DB) |
| `SecretsStore` | `ApollosAISecretsStore` | Encrypted per-user/org secrets | Phase 1 (stub), 2 (DB) |
| `ConversationStore` | `ApollosAIConversationStore` | User+org scoped conversations | Phase 1 (stub), 2 (DB) |
| `UserContext` | `EntraIDUserContextInjector` | V1 native auth context | Phase 1.5 (requires PostgreSQL + MSAL) |

**Week 2-4 (Phase 2-3):**

| Interface | ApollosAI Class | Purpose |
|-----------|----------------|---------|
| `MonitoringListener` | `ApollosAIMonitoringListener` | OpenTelemetry-based |
| `AppConversationInfoServiceInjector` | Org-scoped V1 injector | V1 conversation queries |
| `MCPConfig` | `ApollosAIMCPConfig` | Per-org MCP server management |

### Auth: Keycloak → Entra ID

- **Provider**: MSAL `ConfidentialClientApplication` (not Authlib — Azure `iss` validation bug)
- **User ID**: `oid` claim (stable across App Registrations in tenant, not pairwise `sub`)
- **Cookie**: Same JWT-signed pattern as enterprise, with Entra tokens instead of Keycloak. Required attributes: `HttpOnly=True`, `Secure=True`, `SameSite=Lax`
- **Token storage**: MSAL `SerializableTokenCache` → PostgreSQL, encrypted with AES-256-GCM
- **API keys**: Reuse `ApiKeyStore` pattern (prefix `sk-aai-`, SHA-256 + salt hashed storage)
- **Skip**: GitHub/GitLab OAuth via Keycloak IDP, reCAPTCHA, waitlist, device flow (add later)

### RBAC: Flat → Hierarchical

Enterprise uses Org → User (flat). ApollosAI needs Org → Team → User:

```
Organization (1) ←── (M) Team (M) ←── (M) TeamMembership ──→ (1) User
     │                     │
     └── OrgMembership ────┘── Both have role_id → Role
```

**Roles**: owner(0), admin(1), manager(2), member(3) — rank-based (lower = more privilege)

**Settings resolution**: Organization defaults → Team overrides → TeamMembership per-user overrides

### Storage

- **Database**: PostgreSQL (same as enterprise and Apollos platform)
- **ORM**: SQLAlchemy 2.0+ async via `DbSessionInjector`
- **Encryption**: AES-256-GCM + HKDF (consistent with Apollos platform, not enterprise's JWE/Fernet)
- **Migrations**: Fresh Alembic chain (don't copy enterprise's 92 migrations)
- **Initial migration**: `organization`, `team`, `user`, `role`, `org_membership`, `team_membership`, `auth_tokens`, `api_keys`, `custom_secrets`, `conversation_metadata`, `conversation_ownership`
- **Redis**: Rate limiting only initially; clustered sessions later if multi-server

### Project Structure

```
apollosai/                    # NEW — separate from openhands/
├── app_server.py             # Entrypoint (sets OPENHANDS_CONFIG_CLS)
├── server/
│   ├── config.py             # ApollosAIServerConfig
│   ├── middleware.py          # EntraID auth middleware
│   ├── auth/                 # EntraIDUserAuth, token store, constants
│   └── routes/               # auth, orgs, teams, user, health
├── storage/
│   ├── models/               # organization, team, user, role, memberships, api_key, secrets
│   ├── stores/               # settings, secrets, conversation stores
│   ├── encrypt_utils.py      # AES-256-GCM
│   └── database.py           # DB connection helpers
└── migrations/               # Fresh Alembic chain
```

**Core modifications**: Minimal — only `openhands/app_server/config.py` (load ApollosAI config from env) and `frontend/` (login flow, branding, org/team UI).

**Lint config**: Add `apollosai/` to exclude lists in `dev_config/python/ruff.toml` and `dev_config/python/mypy.ini` (matching the `enterprise/` exclusion pattern). Create `apollosai/dev_config/` for ApollosAI-specific lint rules.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Auth provider | MSAL (Entra ID) | Proven in Apollos platform; Authlib has Azure bugs |
| User ID claim | `oid` | Stable across App Registrations in tenant |
| Database | PostgreSQL | Same as enterprise; already in stack |
| Encryption | AES-256-GCM + HKDF | Consistent with Apollos platform |
| Architecture target | V1 `app_server` | V0 deprecated, removal April 2026 |
| Directory | Separate `apollosai/` | Eases upstream sync |
| Billing | Skip | Internal enterprise tool |
| Experiments | Skip | Not needed |

## Implementation Phases

1. **Foundation** (Week 1-2): Auth + ServerConfig + DB schema + SettingsStore + entrypoint
2. **RBAC & Org Management** (Week 3): CRUD routes, permission middleware, conversation scoping, API keys
3. **Frontend Integration** (Week 4): Login flow, org/team selector, settings pages, branding, i18n
4. **Integrations** (Week 5-6): Slack, custom sandbox config, MCP management
5. **Monitoring & Hardening** (Week 7-8): OTEL, audit logging, rate limiting, security review

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| V0 removal breaks bridge | High | Build V1-native auth context, not just V0 UserAuth |
| Upstream conflicts | Medium | Keep custom code in `apollosai/`, use override pattern |
| MSAL token edge cases | Medium | MSAL has built-in retry/cache; extensive testing |
| Settings resolution complexity | Low | Clear precedence chain; unit test each layer |
| PolyForm license risk | High | Rewrite all code; don't copy verbatim |

## Gaps Identified During Validation

See `.scratchpad/apollosai_ent_research/06-gaps-and-additions.md` for full details:

- 7 undocumented enterprise routes (readiness, email, webhooks, MCP patch, etc.)
- 61 undocumented storage models (repository tracking, conversation callbacks, integration state, etc.)
- Frontend auth needs OIDC support (currently hardcoded for GitHub/GitLab/Bitbucket providers)
- MCP enterprise extension pattern (`SaaSOpenHandsMCPConfig`, `OPENHANDS_MCP_CONFIG_CLS`)
- Microagent MCP tool extension point (`MicroagentMetadata.mcp_tools`)
- Integration Manager pattern is minimal — consider richer base class if building integrations

## Validation Summary

Research accuracy: **27/28 claims verified** against actual codebase (96.4%)

**Corrections applied:**
1. Encryption uses JWE via JwtService (primary), not Fernet (legacy fallback only)
2. BillingSession tracks payment sessions (price/status), not token usage (which lives on conversation_metadata)
3. SaaSMonitoringListener uses GCP structured logging, not PostHog/Datadog directly

## Clean-Room Implementation Process

To mitigate PolyForm license risk, ApollosAI enterprise layer follows a clean-room process:

1. **Research phase**: Enterprise interfaces (ABCs, config patterns, auth flow) were documented from public API surfaces and codebase structure — not by copying implementation code
2. **Implementation phase**: All code is written from scratch against the documented interfaces, using different libraries (MSAL vs Authlib/Keycloak), different encryption (AES-256-GCM vs JWE/Fernet), and different patterns (hierarchical RBAC vs flat)
3. **Verification**: No enterprise source files were used as templates. Structural similarities (e.g., `get_instance` classmethod) derive from implementing the same ABC interface, not from copying enterprise implementations
