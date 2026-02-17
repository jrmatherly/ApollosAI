# Phase 3: Comprehensive Enterprise — Implementation Plan (Index)

> **For Claude:** This is an index file. Each phase is implemented independently in its own plan file. Use superpowers:executing-plans on each sub-plan in order.

**Goal:** Add monitoring/hardening, 5 platform integrations (GitHub, Jira, Slack, Bitbucket, Microsoft 365), per-org MCP with BYOMCP, and full admin frontend panels to the ApollosAI enterprise layer.

**Architecture:** Three pillars built in dependency order: C (Monitoring) -> B (Integrations) -> A (Frontend). Rich base manager pattern for integrations. OTEL-native observability. Env-driven branding.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy async, OpenTelemetry, httpx, slack-sdk, msgraph-sdk, React 19, TanStack Query, Tailwind CSS 4

**Design doc:** `docs/plans/2026-02-17-phase3-design.md`

---

## Implementation Phases

Execute in order. Each phase depends on the previous one.

### Phase 3A: Monitoring & Hardening

**File:** [`2026-02-17-phase3a-monitoring.md`](2026-02-17-phase3a-monitoring.md)
**Tasks:** 1-8 | **Lines:** ~880

| Task | Description |
|------|-------------|
| 1 | AuditLog model with action enum and indexes |
| 2 | IntegrationConfig, IntegrationConversation, UserMCPServer models |
| 3 | Health & readiness endpoints |
| 4 | OTEL tracer/meter initialization with sampling |
| 5 | Monitoring listener (V0 adapter pattern) |
| 6 | Audit log service + record_audit function |
| 7 | Admin audit log query routes |
| 8 | Alembic migrations (2 migrations: monitoring + integrations) |

### Phase 3B: Integration Framework & Platform Connectors

**File:** [`2026-02-17-phase3b-integrations.md`](2026-02-17-phase3b-integrations.md)
**Tasks:** 9-18 | **Lines:** ~630

| Task | Description |
|------|-------------|
| 9 | Integration base models (IntegrationType enum, events, contexts) |
| 10 | Rich base manager (ApollosAIIntegrationManager ABC) |
| 11 | Integration registry + webhook/config routes |
| 12 | GitHub integration manager |
| 13 | Jira integration manager |
| 14 | Slack integration manager |
| 15 | Bitbucket integration manager |
| 16 | Microsoft 365 integration manager |
| 17 | Per-org MCP config with BYOMCP + TTL cache |
| 18 | Python dependency additions |

### Phase 3C: Frontend Admin Panels

**File:** [`2026-02-17-phase3c-frontend.md`](2026-02-17-phase3c-frontend.md)
**Tasks:** 19-32 | **Lines:** ~510

| Task | Description |
|------|-------------|
| 19 | Branding config (backend) |
| 20 | Branding config (frontend useBranding hook) |
| 21 | Admin API service classes |
| 22 | Admin query & mutation hooks |
| 23 | Admin route setup + layout |
| 24 | Admin members panel |
| 25 | Admin integrations panel |
| 26 | Admin MCP panel |
| 27 | Admin audit log viewer |
| 28 | Settings resolution UI |
| 29 | Feature hiding (app_mode) |
| 30 | Wire all routes + final integration |
| 31 | i18n keys |
| 32 | Final pre-commit + full test run |

---

## Review History

- **Initial review:** 59 findings on design doc, 48 on implementation plan (see design doc "Review Amendments" section)
- **Verification:** 16 findings verified against codebase — 13 confirmed, 1 corrected, 1 deferred, 1 not-an-issue
- **Validation review:** 11 additional findings (0 critical, 3 high, 5 medium, 3 low) — see design doc "Validation Review" section

All findings incorporated inline in sub-plans with **REVIEW:** and **REVIEW V2:** prefixes.

---

## Summary

| Phase | Tasks | Key Deliverables |
|-------|-------|-----------------|
| 3A: Monitoring | 1-8 | Audit log, health endpoints, OTEL setup, monitoring listener, migrations |
| 3B: Integrations | 9-18 | Base manager, registry, GitHub/Jira/Slack/Bitbucket/Microsoft managers, MCP config, dependencies |
| 3C: Frontend | 19-32 | Branding, admin API services, hooks, 8 admin panels, settings provenance, feature hiding, i18n |

**Total: 32 tasks across 3 phases, ~60-80 files created/modified**

**Estimated new test count:** ~80-120 tests across backend integration/monitoring/route tests

**Archive:** Full original plan preserved at `2026-02-17-phase3-implementation-full.md`
