# ApollosAI Operational Runbook

## Database Operations

### Backup

```bash
# Docker Compose
docker compose exec postgres pg_dump -U apollosai apollosai > backup_$(date +%Y%m%d_%H%M%S).sql

# Kubernetes
kubectl exec -n apollosai apollosai-postgresql-0 -- pg_dump -U apollosai apollosai > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore

```bash
# Docker Compose
docker compose exec -T postgres psql -U apollosai apollosai < backup_20260218_120000.sql

# Kubernetes
kubectl exec -i -n apollosai apollosai-postgresql-0 -- psql -U apollosai apollosai < backup_20260218_120000.sql
```

### Connection troubleshooting

1. Verify the database is running:
   ```bash
   # Docker Compose
   docker compose exec postgres pg_isready -U apollosai

   # Kubernetes
   kubectl exec -n apollosai apollosai-postgresql-0 -- pg_isready -U apollosai
   ```

2. Check connection count:
   ```bash
   docker compose exec postgres psql -U apollosai -c "SELECT count(*) FROM pg_stat_activity;"
   ```

3. If pool is exhausted, check `SQLALCHEMY_POOL_SIZE` and `SQLALCHEMY_MAX_OVERFLOW` settings. See [Configuration Reference](configuration-reference.md#database-pool).

---

## Rolling Updates

### Docker Compose

```bash
cd deploy/docker-compose
docker compose build app                 # Rebuild app image with latest code
docker compose pull --ignore-buildable   # Update external images (PG, Redis, etc.)
docker compose up -d                     # Recreate changed containers
```

> **Note:** Do not use bare `docker compose pull` — it fails on the app service because
> `apollosai:latest` is built locally, not pulled from a registry.

Migrations run automatically on app startup.

### Helm

```bash
helm upgrade apollosai deploy/helm/apollosai \
  --namespace apollosai \
  -f deploy/helm/apollosai/values-prod.yaml \
  --set existingSecret=apollosai-secrets
```

The migration Job runs as a `pre-upgrade` hook. The Deployment uses a `RollingUpdate` strategy (default: 25% max unavailable).

### Kustomize

```bash
# Update image tag in base/deployment.yaml, then:
kubectl apply -k deploy/k8s/overlays/prod

# If schema changed, run migration first:
kubectl delete job apollosai-migration -n apollosai --ignore-not-found
kubectl apply -k deploy/k8s/overlays/prod
kubectl wait --for=condition=complete job/apollosai-migration -n apollosai --timeout=120s
```

---

## Rollback

### Docker Compose

Pin the previous image tag in `docker-compose.yml`:

```yaml
services:
  app:
    image: ghcr.io/jrmatherly/apollosai/enterprise-server:sha-abc1234
```

Then `docker compose up -d`.

### Helm

```bash
# List revisions
helm history apollosai -n apollosai

# Rollback to previous revision
helm rollback apollosai -n apollosai

# Rollback to specific revision
helm rollback apollosai 3 -n apollosai
```

### Kustomize

```bash
# Revert the image change in git
git revert HEAD
kubectl apply -k deploy/k8s/overlays/prod
```

---

## Scaling

### Manual scaling

```bash
# Docker Compose (single-host only)
docker compose up -d --scale app=3

# Kubernetes
kubectl scale deployment apollosai -n apollosai --replicas=3
```

### HPA configuration

The Helm chart and Kustomize prod overlay include an HPA targeting 80% CPU utilization with 2–10 replicas.

**Note:** CPU-based HPA may not trigger for I/O-bound AI workloads where the app is waiting on LLM API responses. For production, consider custom metrics:
- Active WebSocket connections
- Queued agent tasks
- LLM API request latency (p99)

To use custom metrics, configure a Prometheus adapter or KEDA scaler.

### PodDisruptionBudget

The prod configuration includes a PDB with `minAvailable: 1` to ensure at least one pod remains available during voluntary disruptions (node drains, upgrades).

---

## Log Collection

### Docker Compose

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f app

# Last 100 lines
docker compose logs --tail=100 app
```

### Kubernetes

```bash
# App logs
kubectl logs -n apollosai -l app.kubernetes.io/name=apollosai -f --tail=100

# PostgreSQL logs
kubectl logs -n apollosai apollosai-postgresql-0 -f

# All pods
kubectl logs -n apollosai --all-containers -l app.kubernetes.io/instance=apollosai
```

### Structured logging

ApollosAI outputs structured JSON logs. Key fields:
- `level` — `INFO`, `WARNING`, `ERROR`
- `message` — Human-readable description
- `trace_id` — OTEL trace ID (correlate with Jaeger)
- `timestamp` — ISO 8601 timestamp

---

## Monitoring

### Accessing dashboards

| Service | Docker Compose URL | Purpose |
|---------|-------------------|---------|
| Grafana | `http://localhost:3001` | Dashboards and alerting |
| Jaeger | `http://localhost:16686` | Distributed trace viewer |
| Prometheus | `http://localhost:9090` | Metric queries and alerting |

In Kubernetes, Grafana/Jaeger/Prometheus are not included in the Helm chart or Kustomize manifests (they are Docker Compose only). For K8s observability, install these separately (e.g., via `kube-prometheus-stack` Helm chart) and configure them to scrape the OTEL collector.

### Key metrics to watch

| Metric | Warning Threshold | Critical Threshold |
|--------|------------------|-------------------|
| HTTP error rate (5xx) | > 1% | > 5% |
| HTTP latency p99 | > 5s | > 15s |
| DB connection pool usage | > 80% | > 95% |
| Redis memory usage | > 200MB (of 256MB) | > 240MB |
| Pod restart count | > 2/hour | > 5/hour |
| Disk usage (PG PVC) | > 70% | > 85% |

### Pre-provisioned dashboards

Grafana ships with a pre-provisioned dashboard:
1. **ApollosAI Overview** — HTTP request rate, latency, error rate, active users

---

## Image Version Management

### Checking current versions

```bash
# Docker Compose
docker compose images

# Kubernetes
kubectl get pods -n apollosai -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].image}{"\n"}{end}'
```

### Updating pinned versions

1. Check for new versions:
   ```bash
   # Check GHCR for latest app image
   gh api /users/jrmatherly/packages/container/apollosai%2Fenterprise-server/versions --jq '.[0:5] | .[].metadata.container.tags'

   # Check Docker Hub for dependency updates
   docker pull pgvector/pgvector:0.8.1-pg18  # Verify tag still exists
   ```

2. Update the image tag in:
   - `deploy/docker-compose/docker-compose.yml`
   - `deploy/helm/apollosai/values.yaml` (or override in `values-prod.yaml`)
   - `deploy/k8s/base/deployment.yaml`

3. Test in dev environment first, then promote to production.

### Security updates

Subscribe to security advisories for:
- [PostgreSQL](https://www.postgresql.org/support/security/)
- [Redis](https://github.com/redis/redis/security/advisories)
- [pgvector](https://github.com/pgvector/pgvector/releases)
- [OTEL Collector](https://github.com/open-telemetry/opentelemetry-collector/releases)

---

## Troubleshooting

### Database connection refused

**Symptoms:** App logs show `ConnectionRefusedError` or `could not connect to server`.

**Steps:**
1. Verify PostgreSQL is running: `docker compose ps postgres` or `kubectl get pod apollosai-postgresql-0`
2. Check PG logs: `docker compose logs postgres` or `kubectl logs apollosai-postgresql-0`
3. Verify `DATABASE_URL` hostname matches the service name
4. Check if PG is still initializing (pgvector extension install takes a few seconds on first boot)

### Redis timeout

**Symptoms:** `redis.exceptions.TimeoutError` or `ConnectionError`.

**Steps:**
1. Verify Redis is running and accepting connections: `docker compose exec redis redis-cli -a "$REDIS_PASSWORD" ping`
2. Check memory usage: `docker compose exec redis redis-cli -a "$REDIS_PASSWORD" info memory`
3. If `used_memory` is near `maxmemory` (256MB default), keys are being evicted. Consider increasing `maxmemory` or reducing cache TTLs.

### OTEL collector not receiving data

**Symptoms:** No traces in Jaeger, no metrics in Prometheus.

**Steps:**
1. Verify the OTEL collector is running: `docker compose ps otel-collector`
2. Check collector logs: `docker compose logs otel-collector`
3. Verify `OTEL_EXPORTER_OTLP_ENDPOINT` is set correctly in the app environment
4. Test connectivity: `docker compose exec app curl -sf http://otel-collector:13133/` (health check endpoint)

### Migration failures

**Symptoms:** App fails to start with `alembic` errors, or migration Job shows `Error`/`BackoffLimitExceeded`.

**Steps:**
1. Check migration logs: `docker compose logs app | grep -i migration` or `kubectl logs -n apollosai job/apollosai-migration`
2. Verify `DATABASE_URL` is correct and the database is reachable
3. Check if a previous migration is partially applied: connect to PG and query `SELECT * FROM alembic_version;`
4. If stuck, manually set the version: `UPDATE alembic_version SET version_num = 'target_revision';`

### Connection pool exhaustion

**Symptoms:** `TimeoutError: QueuePool limit of N overflow N reached`, slow responses.

**Steps:**
1. Check current pool usage in Prometheus/Grafana
2. Check active PG connections: `SELECT count(*), state FROM pg_stat_activity GROUP BY state;`
3. Increase `SQLALCHEMY_POOL_SIZE` (recommended: 20) and `SQLALCHEMY_MAX_OVERFLOW` (recommended: 30)
4. If connections are idle, reduce `SQLALCHEMY_POOL_RECYCLE` to reclaim them faster
5. Restart the app to reset the pool: `docker compose restart app`
