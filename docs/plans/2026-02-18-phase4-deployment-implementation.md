# Phase 4: Deployment & Operations — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver production deployment infrastructure for ApollosAI: Docker Compose stack, Helm charts, Kustomize manifests, CI/CD pipelines, and deployment documentation.

**Architecture:** Docker Compose first (7 services: app, Postgres 18 + pgvector, Redis 8, OTEL collector, Jaeger, Prometheus, Grafana), then Helm chart with toggleable sub-resources, then Kustomize as non-Helm alternative, then CI workflows for image publishing and Helm linting.

**Tech Stack:** Docker Compose, Helm 3, Kustomize, GitHub Actions, PostgreSQL 18 (pgvector/pgvector:0.8.1-pg18), Redis 8, OpenTelemetry Collector, Jaeger, Prometheus, Grafana

**Worktree:** `/Users/jason/dev/ApollosAI/.worktrees/phase4` (branch: `feature/phase4-deployment`)

**Design doc:** `docs/plans/2026-02-18-phase4-deployment-design.md`

**Pre-existing state:**
- Root `docker-compose.yml` — simple single-container dev setup (leave as-is)
- `containers/apollosai/Dockerfile` — enterprise image (leave as-is)
- `.env.example` at root — basic env template (leave as-is)
- `apollosai/monitoring/` — OTEL, health, audit already implemented
- 391 ApollosAI unit tests passing

---

## Task 1: Create deploy directory structure

**Files:**
- Create: `deploy/docker-compose/.gitkeep`
- Create: `deploy/docker-compose/otel/.gitkeep`
- Create: `deploy/docker-compose/prometheus/.gitkeep`
- Create: `deploy/docker-compose/grafana/provisioning/.gitkeep`
- Create: `deploy/docker-compose/grafana/dashboards/.gitkeep`
- Create: `deploy/helm/apollosai/templates/.gitkeep`
- Create: `deploy/k8s/base/.gitkeep`
- Create: `deploy/k8s/overlays/dev/.gitkeep`
- Create: `deploy/k8s/overlays/prod/.gitkeep`
- Create: `deploy/docs/.gitkeep`

**Step 1: Create all directories**

```bash
mkdir -p deploy/docker-compose/otel
mkdir -p deploy/docker-compose/prometheus
mkdir -p deploy/docker-compose/grafana/provisioning
mkdir -p deploy/docker-compose/grafana/dashboards
mkdir -p deploy/helm/apollosai/templates
mkdir -p deploy/k8s/base
mkdir -p deploy/k8s/overlays/dev
mkdir -p deploy/k8s/overlays/prod
mkdir -p deploy/docs
```

**Step 2: Commit**

```bash
git add deploy/
git commit -m "chore: scaffold deploy directory structure for Phase 4"
```

---

## Task 2: Docker Compose — environment template

**Files:**
- Create: `deploy/docker-compose/.env.example`

**Step 1: Write the env template**

Create `deploy/docker-compose/.env.example` with all environment variables grouped by category. Every variable must have a comment explaining its purpose, whether it's required or optional, and its default value.

Categories:
- **App Config**: `APP_DISPLAY_NAME=ApollosAI`, `APP_MODE=saas`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`
- **Auth (Entra ID)**: `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET`, `JWT_SECRET` (min 32 chars), `SESSION_SECRET`, `APOLLOSAI_ALLOW_UNAUTHENTICATED=false`
- **Database**: `POSTGRES_USER=apollosai`, `POSTGRES_PASSWORD=apollosai`, `POSTGRES_DB=apollosai`, `DATABASE_URL=postgresql+asyncpg://apollosai:apollosai@postgres:5432/apollosai`
- **Redis**: `REDIS_URL=redis://redis:6379/0`
- **Encryption**: `APOLLOSAI_ENCRYPTION_KEY` (generate with `openssl rand -hex 32`)
- **OTEL**: `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317`, `OTEL_TRACES_SAMPLER=parentbased_traceidratio`, `OTEL_TRACES_SAMPLER_ARG=0.1`, `OTEL_SERVICE_NAME=apollosai`
- **Docker/Sandbox**: `SANDBOX_RUNTIME_CONTAINER_IMAGE`, `WORKSPACE_BASE=./workspace`
- **Grafana**: `GF_SECURITY_ADMIN_USER=admin`, `GF_SECURITY_ADMIN_PASSWORD=admin`

**Step 2: Commit**

```bash
git add deploy/docker-compose/.env.example
git commit -m "feat(deploy): add environment variable template for Docker Compose stack"
```

---

## Task 3: Docker Compose — OTEL collector config

**Files:**
- Create: `deploy/docker-compose/otel/otel-collector-config.yml`

**Step 1: Write OTEL collector config**

The collector receives OTLP from the app and fans out to Jaeger (traces) and Prometheus (metrics).

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 5s
    send_batch_size: 1024
  filter/health:
    traces:
      span:
        - 'attributes["http.route"] == "/health"'
        - 'attributes["http.route"] == "/ready"'

exporters:
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true
  prometheus:
    endpoint: 0.0.0.0:8889
    namespace: apollosai

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

**Step 2: Commit**

```bash
git add deploy/docker-compose/otel/otel-collector-config.yml
git commit -m "feat(deploy): add OTEL collector config with Jaeger and Prometheus exporters"
```

---

## Task 4: Docker Compose — Prometheus config

**Files:**
- Create: `deploy/docker-compose/prometheus/prometheus.yml`
- Create: `deploy/docker-compose/prometheus/alert-rules.yml`

**Step 1: Write Prometheus scrape config**

`deploy/docker-compose/prometheus/prometheus.yml`:
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - alert-rules.yml

scrape_configs:
  - job_name: otel-collector
    static_configs:
      - targets: ['otel-collector:8889']

  - job_name: apollosai-app
    metrics_path: /metrics
    static_configs:
      - targets: ['app:3000']
```

**Step 2: Write alert rules**

`deploy/docker-compose/prometheus/alert-rules.yml`:
```yaml
groups:
  - name: apollosai
    rules:
      - alert: HighErrorRate
        expr: rate(apollosai_http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High HTTP 5xx error rate"
          description: "Error rate is {{ $value }} req/s over the last 5 minutes"

      - alert: HighLatency
        expr: histogram_quantile(0.99, rate(apollosai_http_request_duration_seconds_bucket[5m])) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High p99 latency"
          description: "p99 latency is {{ $value }}s"

      - alert: DatabaseConnectionPoolExhaustion
        expr: apollosai_db_pool_size - apollosai_db_pool_available < 2
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Database connection pool nearly exhausted"

      - alert: AuthFailureSpike
        expr: rate(apollosai_auth_failures_total[5m]) > 1
        for: 3m
        labels:
          severity: warning
        annotations:
          summary: "Auth failure rate spike"
          description: "{{ $value }} auth failures/s over 5 minutes"
```

**Step 3: Commit**

```bash
git add deploy/docker-compose/prometheus/
git commit -m "feat(deploy): add Prometheus scrape config and alert rules"
```

---

## Task 5: Docker Compose — Grafana provisioning

**Files:**
- Create: `deploy/docker-compose/grafana/provisioning/datasources.yml`
- Create: `deploy/docker-compose/grafana/provisioning/dashboards.yml`

**Step 1: Write datasource provisioning**

`deploy/docker-compose/grafana/provisioning/datasources.yml`:
```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false

  - name: Jaeger
    type: jaeger
    access: proxy
    url: http://jaeger:16686
    editable: false
```

**Step 2: Write dashboard provisioning config**

`deploy/docker-compose/grafana/provisioning/dashboards.yml`:
```yaml
apiVersion: 1
providers:
  - name: ApollosAI
    orgId: 1
    folder: ApollosAI
    type: file
    disableDeletion: false
    editable: true
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: false
```

**Step 3: Commit**

```bash
git add deploy/docker-compose/grafana/provisioning/
git commit -m "feat(deploy): add Grafana datasource and dashboard provisioning"
```

---

## Task 6: Docker Compose — Grafana dashboard

**Files:**
- Create: `deploy/docker-compose/grafana/dashboards/apollosai-overview.json`

**Step 1: Write the overview dashboard JSON**

Create a Grafana dashboard JSON with panels for:
- Request rate (req/s) — `rate(apollosai_http_requests_total[5m])`
- Request latency p50/p95/p99 — `histogram_quantile` on `apollosai_http_request_duration_seconds_bucket`
- Error rate by endpoint — `rate(apollosai_http_requests_total{status=~"5.."}[5m])`
- Active conversations gauge — `apollosai_active_conversations`
- Auth success/failure rate — `rate(apollosai_auth_*_total[5m])`
- Integration webhook rate — `rate(apollosai_webhook_requests_total[5m])`

Use standard Grafana dashboard JSON schema. Set `"editable": true` so operators can customize.

The dashboard JSON will be large (~200-300 lines). Include a `__requires` section specifying Grafana >=10.0.0 and Prometheus datasource.

**Step 2: Commit**

```bash
git add deploy/docker-compose/grafana/dashboards/apollosai-overview.json
git commit -m "feat(deploy): add pre-built Grafana overview dashboard"
```

---

## Task 7: Docker Compose — PostgreSQL init script

**Files:**
- Create: `deploy/docker-compose/init-db.sql`

**Step 1: Write the init SQL**

```sql
-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable uuid-ossp for UUID generation (fallback if uuidv7 not available)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

This runs automatically on first `postgres` container start (mounted into `/docker-entrypoint-initdb.d/`).

**Step 2: Commit**

```bash
git add deploy/docker-compose/init-db.sql
git commit -m "feat(deploy): add PostgreSQL init script for pgvector extension"
```

---

## Task 8: Docker Compose — main compose file

**Files:**
- Create: `deploy/docker-compose/docker-compose.yml`

**Step 1: Write the compose file**

7 services with proper healthchecks, depends_on conditions, named volumes, and network isolation.

```yaml
services:
  app:
    build:
      context: ../../
      dockerfile: ./containers/apollosai/Dockerfile
    image: apollosai:latest
    container_name: apollosai-app
    env_file: .env
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - OTEL_EXPORTER_OTLP_ENDPOINT=${OTEL_EXPORTER_OTLP_ENDPOINT}
      - OTEL_SERVICE_NAME=${OTEL_SERVICE_NAME:-apollosai}
      - WORKSPACE_MOUNT_PATH=${WORKSPACE_BASE:-./workspace}
    ports:
      - "3000:3000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ${WORKSPACE_BASE:-./workspace}:/opt/workspace_base
    restart: unless-stopped

  postgres:
    image: pgvector/pgvector:0.8.1-pg18
    container_name: apollosai-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-apollosai}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-apollosai}
      POSTGRES_DB: ${POSTGRES_DB:-apollosai}
    ports:
      - "5432:5432"
    volumes:
      - apollosai-pgdata:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/01-init-extensions.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-apollosai}"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:8
    container_name: apollosai-redis
    command: redis-server --appendonly yes
    ports:
      - "6379:6379"
    volumes:
      - apollosai-redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    container_name: apollosai-otel-collector
    command: ["--config=/etc/otelcol/config.yml"]
    volumes:
      - ./otel/otel-collector-config.yml:/etc/otelcol/config.yml:ro
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
      - "8889:8889"   # Prometheus exporter
    restart: unless-stopped

  jaeger:
    image: jaegertracing/all-in-one:latest
    container_name: apollosai-jaeger
    environment:
      COLLECTOR_OTLP_ENABLED: "true"
    ports:
      - "16686:16686"  # Jaeger UI
      - "4317"         # OTLP gRPC (internal only, collector sends here)
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    container_name: apollosai-prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./prometheus/alert-rules.yml:/etc/prometheus/alert-rules.yml:ro
      - apollosai-prometheus-data:/prometheus
    ports:
      - "9090:9090"
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: apollosai-grafana
    environment:
      GF_SECURITY_ADMIN_USER: ${GF_SECURITY_ADMIN_USER:-admin}
      GF_SECURITY_ADMIN_PASSWORD: ${GF_SECURITY_ADMIN_PASSWORD:-admin}
      GF_USERS_ALLOW_SIGN_UP: "false"
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
      - apollosai-grafana-data:/var/lib/grafana
    ports:
      - "3001:3000"
    depends_on:
      - prometheus
      - jaeger
    restart: unless-stopped

volumes:
  apollosai-pgdata:
  apollosai-redis-data:
  apollosai-prometheus-data:
  apollosai-grafana-data:
```

Key points:
- `app` build context is `../../` (repo root) since compose file is in `deploy/docker-compose/`
- Jaeger's internal OTLP port (4317) is NOT published to host — only `otel-collector` sends to it
- `otel-collector` OTLP port 4317 IS published so the app can reach it via `OTEL_EXPORTER_OTLP_ENDPOINT`
- All data volumes are named for persistence across restarts

**Step 2: Verify syntax**

```bash
cd deploy/docker-compose && docker compose config --quiet
```

**Step 3: Commit**

```bash
git add deploy/docker-compose/docker-compose.yml
git commit -m "feat(deploy): add full Docker Compose stack with 7 services"
```

---

## Task 9: Docker Compose — dev overrides

**Files:**
- Create: `deploy/docker-compose/docker-compose.dev.yml`

**Step 1: Write dev overrides**

```yaml
services:
  app:
    build:
      context: ../../
      dockerfile: ./containers/app/Dockerfile
    environment:
      - DEBUG=1
    volumes:
      - ../../openhands:/app/openhands
      - ../../apollosai:/app/apollosai
    ports:
      - "5678:5678"  # debugpy

  postgres:
    ports:
      - "5432:5432"

  redis:
    ports:
      - "6379:6379"
```

Usage: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up`

**Step 2: Commit**

```bash
git add deploy/docker-compose/docker-compose.dev.yml
git commit -m "feat(deploy): add Docker Compose dev overrides with hot-reload and debug"
```

---

## Task 10: Smoke test — validate Docker Compose stack starts

**Step 1: Copy .env.example to .env and fill in minimal values**

```bash
cd deploy/docker-compose
cp .env.example .env
# Edit .env: set LLM_API_KEY, generate JWT_SECRET and APOLLOSAI_ENCRYPTION_KEY
```

**Step 2: Start the stack**

```bash
docker compose up -d
```

**Step 3: Verify all services healthy**

```bash
docker compose ps
# All 7 services should show "healthy" or "running"
```

**Step 4: Verify app responds**

```bash
curl -s http://localhost:3000/health | jq .
# Expected: {"status": "ok"}
```

**Step 5: Verify Grafana loads**

```bash
curl -s -o /dev/null -w '%{http_code}' http://localhost:3001/login
# Expected: 200
```

**Step 6: Verify Jaeger loads**

```bash
curl -s -o /dev/null -w '%{http_code}' http://localhost:16686
# Expected: 200
```

**Step 7: Tear down**

```bash
docker compose down -v
```

**Step 8: Commit any fixes**

If any config needed adjustment during smoke test, commit the fixes.

---

## Task 11: Helm chart — Chart.yaml and values

**Files:**
- Create: `deploy/helm/apollosai/Chart.yaml`
- Create: `deploy/helm/apollosai/values.yaml`
- Create: `deploy/helm/apollosai/values-dev.yaml`
- Create: `deploy/helm/apollosai/values-prod.yaml`

**Step 1: Write Chart.yaml**

```yaml
apiVersion: v2
name: apollosai
description: ApollosAI — automated AI software engineer platform
type: application
version: 0.1.0
appVersion: "1.0.0"
maintainers:
  - name: Jason Matherly
```

**Step 2: Write values.yaml**

Default values covering all resources. Key sections:
- `image` (repository, tag, pullPolicy)
- `replicaCount` (default: 1)
- `resources` (limits/requests)
- `service` (type: ClusterIP, port: 3000)
- `ingress` (enabled: false)
- `autoscaling` (enabled: false)
- `podDisruptionBudget` (enabled: true, minAvailable: 1)
- `postgresql` (enabled: true, image, persistence size, externalUrl)
- `redis` (enabled: true, image, externalUrl)
- `otelCollector` (enabled: true)
- `env` (non-secret env vars)
- `secrets` (sensitive vars, existingSecret support)
- `migration` (enabled: true, runs as pre-install/pre-upgrade hook)

**Step 3: Write values-dev.yaml**

```yaml
replicaCount: 1
resources:
  limits:
    cpu: "1"
    memory: "2Gi"
  requests:
    cpu: "250m"
    memory: "512Mi"
autoscaling:
  enabled: false
podDisruptionBudget:
  enabled: false
env:
  DEBUG: "1"
```

**Step 4: Write values-prod.yaml**

```yaml
replicaCount: 2
resources:
  limits:
    cpu: "4"
    memory: "8Gi"
  requests:
    cpu: "1"
    memory: "2Gi"
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilization: 70
podDisruptionBudget:
  enabled: true
  minAvailable: 1
ingress:
  enabled: true
```

**Step 5: Commit**

```bash
git add deploy/helm/apollosai/Chart.yaml deploy/helm/apollosai/values.yaml deploy/helm/apollosai/values-dev.yaml deploy/helm/apollosai/values-prod.yaml
git commit -m "feat(deploy): add Helm chart metadata and values files"
```

---

## Task 12: Helm chart — helpers template

**Files:**
- Create: `deploy/helm/apollosai/templates/_helpers.tpl`

**Step 1: Write helpers**

Standard Helm helpers: `apollosai.name`, `apollosai.fullname`, `apollosai.chart`, `apollosai.labels`, `apollosai.selectorLabels`, `apollosai.serviceAccountName`.

**Step 2: Commit**

```bash
git add deploy/helm/apollosai/templates/_helpers.tpl
git commit -m "feat(deploy): add Helm chart helper templates"
```

---

## Task 13: Helm chart — app deployment and service

**Files:**
- Create: `deploy/helm/apollosai/templates/deployment.yaml`
- Create: `deploy/helm/apollosai/templates/service.yaml`

**Step 1: Write deployment template**

Standard Helm Deployment with:
- `{{ .Values.replicaCount }}` replicas
- Container image from `{{ .Values.image.repository }}:{{ .Values.image.tag }}`
- Liveness probe: `httpGet /health` port 3000
- Readiness probe: `httpGet /ready` port 3000
- Resource limits from `{{ .Values.resources }}`
- EnvFrom: ConfigMap + Secret references
- Docker socket volume mount (for sandbox runtime)
- `topologySpreadConstraints` for HA

**Step 2: Write service template**

ClusterIP service on port 3000 targeting the app pods.

**Step 3: Lint**

```bash
helm lint deploy/helm/apollosai/
```

**Step 4: Commit**

```bash
git add deploy/helm/apollosai/templates/deployment.yaml deploy/helm/apollosai/templates/service.yaml
git commit -m "feat(deploy): add Helm app deployment and service templates"
```

---

## Task 14: Helm chart — configmap and secret

**Files:**
- Create: `deploy/helm/apollosai/templates/configmap.yaml`
- Create: `deploy/helm/apollosai/templates/secret.yaml`

**Step 1: Write configmap template**

Non-secret env vars from `{{ .Values.env }}` dict.

**Step 2: Write secret template**

Sensitive env vars from `{{ .Values.secrets }}` dict, base64-encoded. If `{{ .Values.existingSecret }}` is set, skip creation (deployment references the existing secret).

**Step 3: Commit**

```bash
git add deploy/helm/apollosai/templates/configmap.yaml deploy/helm/apollosai/templates/secret.yaml
git commit -m "feat(deploy): add Helm configmap and secret templates"
```

---

## Task 15: Helm chart — ingress, HPA, PDB

**Files:**
- Create: `deploy/helm/apollosai/templates/ingress.yaml`
- Create: `deploy/helm/apollosai/templates/hpa.yaml`
- Create: `deploy/helm/apollosai/templates/pdb.yaml`

**Step 1: Write ingress template**

Conditional on `{{ .Values.ingress.enabled }}`. Supports `className`, `hosts`, `tls`.

**Step 2: Write HPA template**

Conditional on `{{ .Values.autoscaling.enabled }}`. Targets CPU utilization.

**Step 3: Write PDB template**

Conditional on `{{ .Values.podDisruptionBudget.enabled }}`. Uses `minAvailable`.

**Step 4: Commit**

```bash
git add deploy/helm/apollosai/templates/ingress.yaml deploy/helm/apollosai/templates/hpa.yaml deploy/helm/apollosai/templates/pdb.yaml
git commit -m "feat(deploy): add Helm ingress, HPA, and PDB templates"
```

---

## Task 16: Helm chart — PostgreSQL StatefulSet

**Files:**
- Create: `deploy/helm/apollosai/templates/postgres-statefulset.yaml`

**Step 1: Write PostgreSQL StatefulSet**

Conditional on `{{ .Values.postgresql.enabled }}`. Uses `pgvector/pgvector:0.8.1-pg18` image. PVC for data persistence. Healthcheck with `pg_isready`. Init container or initdb script to `CREATE EXTENSION IF NOT EXISTS vector`.

**Step 2: Commit**

```bash
git add deploy/helm/apollosai/templates/postgres-statefulset.yaml
git commit -m "feat(deploy): add Helm PostgreSQL StatefulSet with pgvector"
```

---

## Task 17: Helm chart — Redis deployment

**Files:**
- Create: `deploy/helm/apollosai/templates/redis-deployment.yaml`

**Step 1: Write Redis Deployment**

Conditional on `{{ .Values.redis.enabled }}`. Uses `redis:8` image. Command: `redis-server --appendonly yes`. Healthcheck with `redis-cli ping`.

**Step 2: Commit**

```bash
git add deploy/helm/apollosai/templates/redis-deployment.yaml
git commit -m "feat(deploy): add Helm Redis deployment"
```

---

## Task 18: Helm chart — OTEL collector

**Files:**
- Create: `deploy/helm/apollosai/templates/otel-collector.yaml`

**Step 1: Write OTEL collector deployment + configmap**

Conditional on `{{ .Values.otelCollector.enabled }}`. Embeds the collector config as a ConfigMap (same pipeline as the Docker Compose OTEL config: OTLP receiver → batch processor → Jaeger/Prometheus exporters).

**Step 2: Commit**

```bash
git add deploy/helm/apollosai/templates/otel-collector.yaml
git commit -m "feat(deploy): add Helm OTEL collector deployment"
```

---

## Task 19: Helm chart — migration job

**Files:**
- Create: `deploy/helm/apollosai/templates/migration-job.yaml`

**Step 1: Write migration Job**

Helm hook: `helm.sh/hook: pre-install,pre-upgrade` with `helm.sh/hook-weight: "-5"` (runs before app deployment). Uses the same app image. Command: `alembic -c apollosai/alembic.ini upgrade head`. `restartPolicy: Never`, `backoffLimit: 3`.

**Step 2: Commit**

```bash
git add deploy/helm/apollosai/templates/migration-job.yaml
git commit -m "feat(deploy): add Helm Alembic migration job as pre-install hook"
```

---

## Task 20: Helm chart — validate

**Step 1: Lint the chart**

```bash
helm lint deploy/helm/apollosai/
```

Expected: no errors, possibly info-level messages.

**Step 2: Dry-run template with default values**

```bash
helm template apollosai deploy/helm/apollosai/ > /dev/null
```

**Step 3: Dry-run template with prod values**

```bash
helm template apollosai deploy/helm/apollosai/ -f deploy/helm/apollosai/values-prod.yaml > /dev/null
```

**Step 4: Fix any issues and commit**

---

## Task 21: Kustomize — base manifests

**Files:**
- Create: `deploy/k8s/base/kustomization.yaml`
- Create: `deploy/k8s/base/namespace.yaml`
- Create: `deploy/k8s/base/deployment.yaml`
- Create: `deploy/k8s/base/service.yaml`
- Create: `deploy/k8s/base/configmap.yaml`
- Create: `deploy/k8s/base/secret.yaml`
- Create: `deploy/k8s/base/postgres-statefulset.yaml`
- Create: `deploy/k8s/base/redis-deployment.yaml`
- Create: `deploy/k8s/base/migration-job.yaml`

**Step 1: Write base manifests**

Plain YAML equivalents of the Helm templates with sensible defaults. `kustomization.yaml` lists all resources.

Namespace: `apollosai`. Deployment uses same image, probes, and resource defaults as Helm. Postgres StatefulSet with pgvector init. Redis Deployment with AOF. Migration Job runs before deployment (manual ordering — Kustomize doesn't have hooks).

**Step 2: Validate**

```bash
kubectl kustomize deploy/k8s/base/
```

**Step 3: Commit**

```bash
git add deploy/k8s/base/
git commit -m "feat(deploy): add Kustomize base manifests"
```

---

## Task 22: Kustomize — overlays

**Files:**
- Create: `deploy/k8s/overlays/dev/kustomization.yaml`
- Create: `deploy/k8s/overlays/prod/kustomization.yaml`
- Create: `deploy/k8s/overlays/prod/hpa.yaml`
- Create: `deploy/k8s/overlays/prod/pdb.yaml`

**Step 1: Write dev overlay**

Patches: single replica, lower resources, debug env var.

**Step 2: Write prod overlay**

Patches: 2 replicas, higher resources, HPA, PDB, production env vars.

**Step 3: Validate both**

```bash
kubectl kustomize deploy/k8s/overlays/dev/
kubectl kustomize deploy/k8s/overlays/prod/
```

**Step 4: Commit**

```bash
git add deploy/k8s/overlays/
git commit -m "feat(deploy): add Kustomize dev and prod overlays"
```

---

## Task 23: CI workflow — Docker image publish

**Files:**
- Create: `.github/workflows/docker-publish.yml`

**Step 1: Write the workflow**

Triggers: push to `main`, tags matching `v*`.

Jobs:
1. **build-and-push**: Build `apollosai` image, smoke test (`/health` returns 200), push to `ghcr.io/jrmatherly/apollosai` with tags `latest`, `sha-<short>`, and `v<semver>` (if tag).

Uses: `docker/setup-buildx-action`, `docker/login-action` (GHCR), `docker/build-push-action`.

Smoke test: start container with `--health-cmd`, wait for healthy, `curl /health`.

**Step 2: Commit**

```bash
git add .github/workflows/docker-publish.yml
git commit -m "feat(ci): add Docker image build and publish workflow"
```

---

## Task 24: CI workflow — Helm lint

**Files:**
- Create: `.github/workflows/helm-lint.yml`

**Step 1: Write the workflow**

Triggers: PR changes to `deploy/helm/**`.

Jobs:
1. **helm-lint**: Install Helm, run `helm lint`, run `helm template` with default and prod values.

Uses: `azure/setup-helm@v4`.

**Step 2: Commit**

```bash
git add .github/workflows/helm-lint.yml
git commit -m "feat(ci): add Helm lint workflow for PR validation"
```

---

## Task 25: Deployment guide

**Files:**
- Create: `deploy/docs/deployment-guide.md`

**Step 1: Write deployment guide**

Sections:
1. **Prerequisites** — Docker 24+, Docker Compose v2, K8s 1.28+ (for K8s), Helm 3.14+ (for Helm), Entra ID app registration
2. **Quick Start (Docker Compose)** — Copy `.env.example`, fill values, `docker compose up -d`, verify with `curl /health`
3. **Kubernetes — Helm** — `helm install`, configure values, verify pods
4. **Kubernetes — Kustomize** — `kubectl apply -k`, configure overlays
5. **First-Time Setup** — Run migrations, create initial admin user
6. **TLS Configuration** — Ingress TLS, cert-manager integration
7. **Upgrading** — Pull new image, migrations run automatically (Helm hook or manual for Kustomize)

**Step 2: Commit**

```bash
git add deploy/docs/deployment-guide.md
git commit -m "docs(deploy): add deployment guide for Docker Compose and Kubernetes"
```

---

## Task 26: Configuration reference

**Files:**
- Create: `deploy/docs/configuration-reference.md`

**Step 1: Write configuration reference**

Table format with columns: Variable, Required, Default, Description, Category.

Group by category: App, Auth, Database, Redis, Encryption, OTEL, Docker/Sandbox, Grafana, Integrations.

Source truth from: `.env.example` files, `apollosai/server/config.py`, `apollosai/server/auth/constants.py`, `apollosai/monitoring/otel.py`.

**Step 2: Commit**

```bash
git add deploy/docs/configuration-reference.md
git commit -m "docs(deploy): add configuration reference for all environment variables"
```

---

## Task 27: Operational runbook

**Files:**
- Create: `deploy/docs/runbook.md`

**Step 1: Write runbook**

Sections:
1. **Database Operations** — Backup (`pg_dump`), restore, connection troubleshooting
2. **Rolling Updates** — Docker Compose (`docker compose pull && docker compose up -d`), Helm (`helm upgrade`), Kustomize (`kubectl apply`)
3. **Rollback** — Docker Compose (pin previous image tag), Helm (`helm rollback`), Kustomize (git revert + apply)
4. **Scaling** — Manual replica adjustment, HPA configuration
5. **Log Collection** — Docker logs, K8s pod logs, structured log format
6. **Monitoring** — Accessing Grafana/Jaeger/Prometheus, key metrics to watch
7. **Troubleshooting** — Common issues: DB connection refused, Redis timeout, OTEL not receiving data, migration failures

**Step 2: Commit**

```bash
git add deploy/docs/runbook.md
git commit -m "docs(deploy): add operational runbook for ApollosAI deployments"
```

---

## Task 28: Final validation and PR

**Step 1: Run pre-commit on all files**

```bash
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml
```

**Step 2: Verify ApollosAI tests still pass**

```bash
poetry run pytest tests/unit/apollosai/ -v --tb=short
```

Expected: 391 tests passing (no regressions — Phase 4 adds no Python code).

**Step 3: Verify Helm lint passes**

```bash
helm lint deploy/helm/apollosai/
```

**Step 4: Push and create PR**

```bash
git push -u origin feature/phase4-deployment
gh pr create --title "feat(deploy): Phase 4 — deployment infrastructure" --body "$(cat <<'EOF'
## Summary
- Full Docker Compose stack: app + PostgreSQL 18 (pgvector) + Redis 8 + OTEL collector + Jaeger + Prometheus + Grafana
- Helm chart with toggleable infrastructure (Postgres, Redis, OTEL), HPA, PDB, migration hooks
- Kustomize base + dev/prod overlays as non-Helm alternative
- CI workflows: Docker image publish (GHCR) + Helm lint
- Deployment guide, configuration reference, and operational runbook

## Test plan
- [ ] `docker compose config --quiet` validates compose syntax
- [ ] `helm lint deploy/helm/apollosai/` passes
- [ ] `helm template` dry-run succeeds with default and prod values
- [ ] `kubectl kustomize deploy/k8s/base/` renders valid YAML
- [ ] `kubectl kustomize deploy/k8s/overlays/prod/` renders valid YAML
- [ ] Docker Compose stack starts and `/health` returns 200
- [ ] Grafana loads at :3001 with pre-provisioned dashboard
- [ ] 391 ApollosAI unit tests still pass (no regressions)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
