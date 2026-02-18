# ApollosAI Phase 4: Deployment & Operations — Design Document

> Date: 2026-02-18
> Status: Approved
> Depends on: Phase 1/1.5 (PR #1, merged), Phase 2 (PR #5, merged), Phase 3A+3B (PR #7, merged), Phase 3C (PR #9, merged)

## Purpose

Phase 4 delivers the deployment infrastructure to run ApollosAI in production. This includes a full Docker Compose stack (app + PostgreSQL 18 + Redis 8 + OTEL observability), Helm charts for on-prem Kubernetes, Kustomize manifests as a non-Helm alternative, CI/CD pipelines for image builds, and deployment documentation.

ApollosAI is an internal enterprise tool — there is no billing or subscription layer. All deployment artifacts treat ApollosAI as the default product (no "enterprise" qualifier).

## Context

**What exists today:**
- `docker-compose.yml` at repo root — single-container dev setup (app only, no Postgres/Redis/OTEL)
- `containers/apollosai/Dockerfile` — enterprise image that layers `apollosai/` onto the base OpenHands image
- `containers/app/Dockerfile` — base OpenHands app image
- `apollosai/monitoring/otel.py` — OTEL instrumentation (traces, metrics) configured via `OTEL_EXPORTER_OTLP_ENDPOINT`
- `apollosai/monitoring/health.py` — `/health` and `/ready` endpoints
- `apollosai/monitoring/audit.py` — audit logging to PostgreSQL
- `apollosai/server/rate_limit.py` — slowapi rate limiting with optional Redis backend
- `.env.example` at repo root — basic env template
- `.github/workflows/ghcr-build.yml` — existing image build workflow

**What Phase 4 adds:**
- Full-stack Docker Compose (7 services) with observability pre-configured
- Helm chart for on-prem Kubernetes deployment
- Kustomize base + overlays as non-Helm alternative
- CI workflows for image publishing and Helm linting
- Deployment guide, configuration reference, and operational runbook

## Architecture

### Approach: Docker Compose First, Then Kubernetes

Build the full Docker Compose stack first, validate it works end-to-end, then layer Kubernetes manifests on top. The compose stack doubles as the local development environment for Phase 5 (integration testing needs real Postgres/Redis) and Phase 6 (E2E tests need a running system).

### Directory Structure

```
deploy/
├── docker-compose/
│   ├── docker-compose.yml              # Full ApollosAI stack (7 services)
│   ├── docker-compose.dev.yml          # Dev overrides (hot-reload, debug)
│   ├── .env.example                    # Complete env template
│   ├── otel/
│   │   └── otel-collector-config.yml   # OTEL collector pipeline config
│   ├── prometheus/
│   │   ├── prometheus.yml              # Scrape targets
│   │   └── alert-rules.yml            # Prometheus alert rules
│   └── grafana/
│       ├── provisioning/
│       │   ├── datasources.yml         # Auto-provision Prometheus + Jaeger
│       │   └── dashboards.yml          # Auto-provision dashboard dir
│       └── dashboards/
│           └── apollosai-overview.json  # Pre-built overview dashboard
├── helm/
│   └── apollosai/
│       ├── Chart.yaml
│       ├── values.yaml                 # Default values
│       ├── values-dev.yaml             # Dev overrides
│       ├── values-prod.yaml            # Production overrides
│       └── templates/
│           ├── deployment.yaml
│           ├── service.yaml
│           ├── ingress.yaml
│           ├── configmap.yaml
│           ├── secret.yaml
│           ├── hpa.yaml
│           ├── pdb.yaml
│           ├── postgres-statefulset.yaml
│           ├── redis-deployment.yaml
│           ├── otel-collector.yaml
│           ├── migration-job.yaml
│           └── _helpers.tpl
├── k8s/
│   ├── base/
│   │   ├── kustomization.yaml
│   │   ├── namespace.yaml
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── configmap.yaml
│   │   ├── secret.yaml
│   │   ├── postgres-statefulset.yaml
│   │   ├── redis-deployment.yaml
│   │   └── migration-job.yaml
│   └── overlays/
│       ├── dev/
│       │   └── kustomization.yaml
│       └── prod/
│           └── kustomization.yaml
└── docs/
    ├── deployment-guide.md
    ├── configuration-reference.md
    └── runbook.md
```

The existing root `docker-compose.yml` remains as-is (simple single-container dev setup).

## Docker Compose Stack

### Services

| Service | Image | Purpose | Ports |
|---------|-------|---------|-------|
| `app` | `apollosai:latest` | ApollosAI backend + frontend | 3000 |
| `postgres` | `pgvector/pgvector:0.8.1-pg18` | Primary database with vector search | 5432 |
| `redis` | `redis:8` | Rate limiting, session cache | 6379 |
| `otel-collector` | `otel/opentelemetry-collector-contrib` | Receives OTEL traces/metrics, fans out | 4317, 4318 |
| `jaeger` | `jaegertracing/all-in-one` | Distributed tracing UI | 16686 |
| `prometheus` | `prom/prometheus` | Metrics storage + alerting | 9090 |
| `grafana` | `grafana/grafana` | Dashboards + visualization | 3001 |

### Data Flow

```
app → OTLP (gRPC:4317) → otel-collector → jaeger (traces)
                                         → prometheus (metrics)
prometheus → grafana (dashboards)
jaeger → grafana (trace links)
```

### PostgreSQL 18 + pgvector

- **Image**: `pgvector/pgvector:0.8.1-pg18` — PostgreSQL 18 with pgvector 0.8.1 pre-installed
- **PG18 benefits**: Async I/O (io_uring) with up to 3x storage read improvements, OAuth 2.0 auth support, `uuidv7()` for time-sortable UUIDs, planner statistics preserved across major upgrades
- **pgvector 0.8.1**: Iterative index scans for filtered vector queries, supports HNSW and IVFFlat indexes
- **Init script**: `CREATE EXTENSION IF NOT EXISTS vector;` — enables future RAG/embedding workflows
- **Persistence**: Named volume `apollosai-pgdata`

### Redis 8

- **Image**: `redis:8` (current: 8.2.4, Feb 2026)
- **Redis 8 changes**: Integrates Redis Query Engine, JSON, TimeSeries, and probabilistic data structures natively. New `io-threads` config for multi-core throughput
- **Security model**: Auto-drops privileges to `redis` user, auto-fixes data dir permissions (8.0.2+) — no manual `chown` needed
- **Config model**: Redis 8 has `redis.conf` (server only) vs `redis-full.conf` (server + modules). We use `redis.conf` (caching/rate-limiting only)
- **AOF**: `appendonly yes` unchanged from Redis 7
- **ACL**: New categories (`@search`, `@json`, etc.) don't affect default user usage

### Healthchecks

All services use Docker healthchecks. The `app` service depends on `postgres` and `redis` with `condition: service_healthy`.

```yaml
postgres:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U apollosai"]
    interval: 5s
    timeout: 5s
    retries: 5

redis:
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s
    timeout: 5s
    retries: 5
```

### Dev Overrides

`docker-compose.dev.yml` adds:
- Source code mount for hot-reload
- `DEBUG=1` environment variable
- Additional debug ports
- Lower resource limits

### Environment Template

`deploy/docker-compose/.env.example` covers all categories:
- **App**: `APP_DISPLAY_NAME`, `APP_MODE=saas`, `LLM_MODEL`, `LLM_API_KEY`
- **Auth**: `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET`, `JWT_SECRET` (min 32 chars), `SESSION_SECRET`
- **Database**: `DATABASE_URL=postgresql+asyncpg://apollosai:apollosai@postgres:5432/apollosai`
- **Redis**: `REDIS_URL=redis://redis:6379/0`
- **OTEL**: `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317`, `OTEL_TRACES_SAMPLER=parentbased_traceidratio`, `OTEL_TRACES_SAMPLER_ARG=0.1`
- **Encryption**: `APOLLOSAI_ENCRYPTION_KEY`
- **Docker**: `SANDBOX_RUNTIME_CONTAINER_IMAGE`, `WORKSPACE_BASE`

## OTEL Collector Pipeline

The collector receives OTLP data from the app and fans out:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

exporters:
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true
  prometheus:
    endpoint: 0.0.0.0:8889

processors:
  batch:
    timeout: 5s
    send_batch_size: 1024
  filter/health:
    traces:
      span:
        - 'attributes["http.route"] == "/health"'
        - 'attributes["http.route"] == "/ready"'

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [filter/health, batch]
      exporters: [otlp/jaeger]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
```

Health probe endpoints (`/health`, `/ready`) are filtered from traces to reduce noise.

## Prometheus & Grafana

### Prometheus

- Scrapes OTEL collector's Prometheus exporter endpoint
- Alert rules for: high error rate, DB connection pool exhaustion, auth failure spikes, high latency p99
- Alertmanager config is optional (can route to Slack via existing Slack integration)

### Grafana

Auto-provisioned with:
- **Datasources**: Prometheus (metrics) + Jaeger (traces)
- **Dashboard**: `apollosai-overview.json` — pre-built dashboard with panels for:
  - Request rate + latency (p50/p95/p99)
  - Error rate by endpoint
  - Active conversations
  - Database query latency
  - Auth success/failure rate
  - Integration webhook processing rate

## Helm Chart

### Design Principles

- **Toggleable infrastructure**: Postgres, Redis, OTEL collector can each be disabled when using external services (`postgresql.enabled: false` + `externalDatabase.url`)
- **Secret management**: Supports both inline secrets and `existingSecret` references for external secret management (Vault, Sealed Secrets, etc.)
- **Probes**: Uses existing `/health` (liveness) and `/ready` (readiness) endpoints
- **Migration Job**: Alembic `upgrade head` runs as a Helm pre-install/pre-upgrade hook

### values.yaml Key Sections

```yaml
image:
  repository: ghcr.io/jrmatherly/apollosai
  tag: latest
  pullPolicy: IfNotPresent

replicaCount: 1

resources:
  limits:
    cpu: "2"
    memory: "4Gi"
  requests:
    cpu: "500m"
    memory: "1Gi"

postgresql:
  enabled: true              # Set false to use external DB
  image: pgvector/pgvector:0.8.1-pg18
  persistence:
    size: 20Gi
  externalUrl: ""            # Used when enabled=false

redis:
  enabled: true
  image: redis:8
  externalUrl: ""

otelCollector:
  enabled: true

ingress:
  enabled: false
  className: "nginx"
  hosts: []
  tls: []

autoscaling:
  enabled: false
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilization: 70

podDisruptionBudget:
  enabled: true
  minAvailable: 1
```

### values-dev.yaml

Lower resources, single replica, debug logging, no HPA.

### values-prod.yaml

Higher resources, 2+ replicas, HPA enabled, PDB enabled, production ingress.

## Kustomize (Non-Helm Alternative)

Plain YAML manifests in `deploy/k8s/` for teams that don't use Helm:

- **`base/`**: Vanilla manifests (Deployment, Service, ConfigMap, Secret, Postgres StatefulSet, Redis Deployment, Migration Job)
- **`overlays/dev/`**: Lower resource limits, single replica, debug logging
- **`overlays/prod/`**: Higher limits, HPA, PDB, production ingress

Kustomize patches handle environment-specific overrides. Same resources as Helm but declarative YAML.

## CI/CD Pipelines

### Image Publishing: `.github/workflows/docker-publish.yml`

**Triggers**: Push to `main`, version tags (`v*`)

**Steps**:
1. Build `apollosai` image using `containers/apollosai/Dockerfile`
2. Smoke test: container starts, `/health` returns 200
3. Push to `ghcr.io/jrmatherly/apollosai` with tags: `latest`, `sha-<short>`, `v<semver>` (if tag push)

### Helm Lint: `.github/workflows/helm-lint.yml`

**Triggers**: PR changes to `deploy/helm/**`

**Steps**:
1. `helm lint deploy/helm/apollosai/`
2. `helm template` dry-run with default values
3. `helm template` dry-run with `values-prod.yaml`

## Deployment Documentation

### `deploy/docs/deployment-guide.md`

Step-by-step for both deployment targets:
- Prerequisites (Docker, K8s cluster, Entra ID app registration)
- Quick start with Docker Compose
- K8s deployment (Helm install / Kustomize apply)
- First-time setup (run migrations, create admin user)
- TLS/ingress configuration

### `deploy/docs/configuration-reference.md`

Every environment variable documented:
- Required vs optional
- Default values
- Format/validation rules
- Grouped by category (auth, database, integrations, monitoring, runtime)

### `deploy/docs/runbook.md`

Operational procedures:
- Database backup/restore
- Rolling updates / rollbacks
- Scaling (manual + HPA)
- Log collection and analysis
- Common troubleshooting scenarios

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| PostgreSQL version | 18 with pgvector | Async I/O improvements, vector search for future RAG/embeddings |
| Redis version | 8 | Integrated modules, io-threads, improved security defaults |
| Compose location | `deploy/docker-compose/` | Keeps repo root clean; existing root compose stays as-is |
| K8s approach | Both Helm and Kustomize | Different teams prefer different tools; low incremental cost |
| Migration strategy | Helm pre-install/pre-upgrade hook | Migrations run before app starts, prevents schema drift |
| Secret management | `existingSecret` support | Works with Vault, Sealed Secrets, or inline — flexible for any org |
| Observability | OTEL collector fan-out | Single ingestion point; traces to Jaeger, metrics to Prometheus |
| Health probe filtering | OTEL processor filter | Prevents /health and /ready from polluting trace data |

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| PG18 + pgvector compatibility | Low | Using official `pgvector/pgvector:0.8.1-pg18` image (actively maintained) |
| Redis 8 ACL breaking changes | Low | Using default user; ACL category changes only affect custom ACL rules |
| Helm chart complexity | Medium | Start simple; toggleable sub-charts keep it manageable |
| Docker socket mount security | High | Document security implications; recommend rootless Docker or Sysbox for production |

---

## Phase 5 & 6 Placeholder Prompts

### Phase 5: Integration Deepening (Future)

Use the following prompt to start Phase 5 in a new session:

```
/sc:load activate and load this project using Serena

I'm starting Phase 5: Integration Deepening for ApollosAI.

Context:
- Phase 4 (Deployment & Ops) is complete — full Docker Compose stack, Helm charts, K8s manifests, CI/CD pipelines
- The deploy/docker-compose/ stack provides Postgres 18 + pgvector, Redis 8, OTEL collector, Jaeger, Prometheus, Grafana
- 5 integration managers exist as framework-level stubs (~150-225 lines each): GitHub, Jira, Slack, Bitbucket, Microsoft 365
- Each has a manager.py, service.py, and views.py but likely lacks real API client implementations
- The base manager (apollosai/integrations/base.py) provides HTTP client, credential store, webhook verification, OTEL tracing
- ApollosAI is an internal enterprise tool — no billing

Task: Brainstorm and design Phase 5 to make all 5 integration stubs into real, functional implementations with:
1. Real API clients (OAuth flows, token management, API calls)
2. Real webhook handlers (signature verification, event parsing, conversation creation)
3. Real response posting (comments on PRs/issues, Slack thread replies, etc.)
4. Integration tests that run against the Phase 4 Docker Compose stack

Start by reading the current integration code, studying the enterprise integration patterns for reference, and then run /superpowers:brainstorming to design Phase 5.
```

### Phase 6: Production Readiness (Future)

Use the following prompt to start Phase 6 in a new session:

```
/sc:load activate and load this project using Serena

I'm starting Phase 6: Production Readiness for ApollosAI.

Context:
- Phase 4 (Deployment & Ops) is complete — full Docker Compose stack, Helm charts, K8s manifests, CI/CD
- Phase 5 (Integration Deepening) is complete — all 5 integrations have real API clients and webhook handlers
- ApollosAI has 391+ unit tests but no E2E tests, no API docs, and no production observability dashboards
- ApollosAI is an internal enterprise tool — no billing

Task: Brainstorm and design Phase 6 to achieve production readiness with:
1. E2E test suite (Playwright) covering: auth flow, conversation creation, admin panels, integration config
2. OpenAPI spec generation from FastAPI routes (auto-generated + manual enrichment)
3. Grafana dashboard expansion (per-integration metrics, user activity, conversation lifecycle)
4. Load testing setup (Locust or k6) targeting key endpoints
5. Deployment documentation validation (run through the deployment guide, fix gaps)

Start by reading the current test infrastructure, examining the FastAPI route definitions, and reviewing the Grafana dashboard from Phase 4. Then run /superpowers:brainstorming to design Phase 6.
```
