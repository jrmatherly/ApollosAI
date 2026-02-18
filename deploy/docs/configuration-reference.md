# ApollosAI Configuration Reference

All configuration is via environment variables. In Docker Compose, set these in `deploy/docker-compose/.env`. In Kubernetes, set them in ConfigMaps and Secrets (Helm `values.yaml` or Kustomize `configmap.yaml`/`.env`).

---

## App

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_DISPLAY_NAME` | No | `ApollosAI` | Display name shown in the UI |
| `APP_MODE` | No | `saas` | Application mode (`saas`, `openhands`) |
| `LLM_MODEL` | Yes | — | LLM model identifier (e.g., `anthropic/claude-sonnet-4-20250514`) |
| `LLM_API_KEY` | Yes | — | API key for the LLM provider |
| `LLM_BASE_URL` | No | — | Custom base URL for LLM API (for self-hosted or proxy setups) |

## Auth (Microsoft Entra ID)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENTRA_TENANT_ID` | Cond. | — | Entra ID tenant ID. Required unless `APOLLOSAI_ALLOW_UNAUTHENTICATED=true` |
| `ENTRA_CLIENT_ID` | Cond. | — | Entra ID application (client) ID. Required unless `APOLLOSAI_ALLOW_UNAUTHENTICATED=true` |
| `ENTRA_CLIENT_SECRET` | No | — | Entra ID client secret (for confidential client flows) |
| `JWT_SECRET` | Yes | — | JWT signing secret. **Minimum 32 characters.** Generate: `openssl rand -hex 32` |
| `SESSION_SECRET` | Yes | — | Starlette SessionMiddleware signing secret. Must differ from `JWT_SECRET`. Generate: `openssl rand -hex 32` |
| `APOLLOSAI_ALLOW_UNAUTHENTICATED` | No | `false` | Skip auth for local dev. Parsed explicitly: only `1`, `true`, `yes` (case-insensitive) enable it |

## Database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_USER` | No | `apollosai` | PostgreSQL username |
| `POSTGRES_PASSWORD` | Yes | — | PostgreSQL password. **Change before production.** |
| `POSTGRES_DB` | No | `apollosai` | PostgreSQL database name |
| `DATABASE_URL` | Yes | — | Full async connection string. Format: `postgresql+asyncpg://USER:PASS@HOST:5432/DB`. In Docker Compose, the hostname is `postgres` (the service name). Adjust for external databases. |

## Database Pool

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SQLALCHEMY_POOL_SIZE` | No | `5` | Connection pool size. **Recommended: `20`** for AI workloads that hold connections during long-running LLM API calls |
| `SQLALCHEMY_MAX_OVERFLOW` | No | `10` | Max connections above pool size during bursts. Recommended: `30` |
| `SQLALCHEMY_POOL_RECYCLE` | No | `3600` | Recycle connections after N seconds. Recommended: `1800` to avoid stale PG connections |

## Redis

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_PASSWORD` | Yes | — | Redis authentication password. **Never run Redis without a password.** |
| `REDIS_URL` | Yes | — | Full Redis connection string. Format: `redis://:PASSWORD@HOST:6379/0`. In Docker Compose, the hostname is `redis`. |

## Encryption

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APOLLOSAI_ENCRYPTION_KEY` | Yes | — | Field-level encryption key for sensitive data at rest. Generate: `openssl rand -hex 32` |

## OpenTelemetry

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | — | OTLP exporter endpoint. In Docker Compose: `http://otel-collector:4317`. Set to enable tracing/metrics. |
| `OTEL_TRACES_SAMPLER` | No | `parentbased_always_on` | Trace sampling strategy. Use `parentbased_traceidratio` for production |
| `OTEL_TRACES_SAMPLER_ARG` | No | `1.0` | Sampling ratio (0.0–1.0). Use `0.1` (10%) for production to control volume |
| `OTEL_SERVICE_NAME` | No | `apollosai` | Service name in traces and metrics |

## Docker / Sandbox

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SANDBOX_RUNTIME_CONTAINER_IMAGE` | No | — | Custom runtime container image for AI agent sandboxes |
| `WORKSPACE_BASE` | No | `./workspace` | Base directory for agent workspaces |

## Grafana

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GF_SECURITY_ADMIN_USER` | No | `admin` | Grafana admin username |
| `GF_SECURITY_ADMIN_PASSWORD` | Yes | — | Grafana admin password. **Change before production.** |

---

## Notes

- **Docker Compose hostnames**: Variables like `DATABASE_URL` and `REDIS_URL` use Docker Compose service names (`postgres`, `redis`, `otel-collector`) as hostnames. For non-Docker deployments, replace with actual hostnames or IP addresses.
- **Pool sizing**: The default SQLAlchemy async pool of 5 connections is insufficient for AI workloads. Set `SQLALCHEMY_POOL_SIZE=20` and `SQLALCHEMY_MAX_OVERFLOW=30` for production.
- **PostgreSQL storage**: The default PVC size is 20Gi. For production with many users, increase to 50Gi+ (set in Helm `values-prod.yaml` or Kustomize prod overlay).
- **Secrets management**: In Kubernetes, use `existingSecret` (Helm) or Kustomize `secretGenerator` to inject secrets. Never bake secrets into container images or pass them as build args.
