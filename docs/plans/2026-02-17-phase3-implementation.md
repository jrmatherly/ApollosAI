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

### Phase 3C: Frontend Admin Panels + Review Remediation

**File:** [`2026-02-17-phase3c-frontend.md`](2026-02-17-phase3c-frontend.md)
**Tasks:** 19-37 | **Lines:** ~700

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
| 27 | Admin audit log viewer (amended: M8 pagination prerequisite) |
| 28 | Settings resolution UI |
| 29 | Feature hiding (app_mode) |
| 30 | Wire all routes + final integration (amended: M4 CORS, L1 error messages, stale class name fix) |
| 31 | **NEW** MCP config cache safety (H6, L5) |
| 32 | **NEW** Audit pagination backend (M8) |
| 33 | **NEW** Service client refactor (H5, M3, H7, H9) |
| 34 | **NEW** Replay protection + payload safety (M1, M5) |
| 35 | **NEW** Resolve encryption TODOs (C3) |
| 36 | i18n keys (was 31) |
| 37 | Final pre-commit + full test run + cleanup (was 32, amended: L4, L7) |

---

## Review History

- **Initial review:** 59 findings on design doc, 48 on implementation plan (see design doc "Review Amendments" section)
- **Verification:** 16 findings verified against codebase — 13 confirmed, 1 corrected, 1 deferred, 1 not-an-issue
- **Validation review:** 11 additional findings (0 critical, 3 high, 5 medium, 3 low) — see design doc "Validation Review" section
- **Phase 3 code review:** 32 findings (4 Critical, 9 High, 11 Medium, 8 Low) from 3-agent parallel review — see `.scratchpad/phase3-review-findings.md`
  - 9 must-fix/should-fix findings addressed in `.scratchpad/2026-02-17-phase3-review-fixes.md` (C1, C2, C4, H1, H2, H3, H4, H8, C3)
  - 14 deferred findings incorporated into Phase 3C as Tasks 31-35 + amendments to Tasks 27, 30, 37
  - 8 findings accepted as-is (M2, M6, M7, M9, M10, M11, L2, L3)
  - 1 finding deferred pending investigation (L8 Jira HMAC)

All findings incorporated inline in sub-plans with **REVIEW:** and **REVIEW V2:** prefixes.

---

## Summary

| Phase | Tasks | Key Deliverables |
|-------|-------|-----------------|
| 3A: Monitoring | 1-8 | Audit log, health endpoints, OTEL setup, monitoring listener, migrations |
| 3B: Integrations | 9-18 | Base manager, registry, GitHub/Jira/Slack/Bitbucket/Microsoft managers, MCP config, dependencies |
| 3C: Frontend + Review | 19-37 | Branding, admin API services, hooks, 8 admin panels, settings provenance, feature hiding, review remediation (cache safety, pagination, client refactor, replay protection, encryption), i18n |

**Total: 37 tasks across 3 phases, ~70-90 files created/modified**

**Review coverage:** 9 of 32 findings addressed in PR #7, 14 planned for Phase 3C (Tasks 31-35 + amendments). 8 accepted as-is. 1 deferred.

**Estimated new test count:** ~100-140 tests across backend integration/monitoring/route/validation tests

**Archive:** Full original plan preserved at `2026-02-17-phase3-implementation-full.md`
