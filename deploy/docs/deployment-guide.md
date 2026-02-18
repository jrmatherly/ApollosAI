# ApollosAI Deployment Guide

## Prerequisites

| Component | Minimum Version | Required For |
|-----------|----------------|--------------|
| Docker | 24+ | Docker Compose deployments |
| Docker Compose | v2 | Docker Compose deployments |
| Kubernetes | 1.28+ | K8s deployments |
| Helm | 3.14+ | Helm chart deployments |
| kubectl | 1.28+ | Kustomize deployments |
| PostgreSQL | 16+ (18 recommended) | All deployments |
| Redis | 7+ (8 recommended) | All deployments |

**Optional:** Microsoft Entra ID app registration (for SSO authentication). Set `APOLLOSAI_ALLOW_UNAUTHENTICATED=true` to skip auth for local development.

---

## Quick Start (Docker Compose)

### 1. Build or pull images

The ApollosAI enterprise image (`containers/apollosai/Dockerfile`) requires the base OpenHands image as a build dependency. Either:

```bash
# Option A: Pull pre-built images from GHCR
docker pull ghcr.io/jrmatherly/openhands:main
docker pull ghcr.io/jrmatherly/apollosai/enterprise-server:main

# Option B: Build locally
./containers/build.sh -i openhands
./containers/build.sh -i apollosai
```

### 2. Configure environment

```bash
cd deploy/docker-compose
cp .env.example .env
```

Edit `.env` and replace all `CHANGE_ME_BEFORE_PRODUCTION` values:
- `JWT_SECRET` — generate with `openssl rand -hex 32`
- `SESSION_SECRET` — generate with `openssl rand -hex 32`
- `POSTGRES_PASSWORD` — strong database password
- `REDIS_PASSWORD` — strong Redis password
- `APOLLOSAI_ENCRYPTION_KEY` — generate with `openssl rand -hex 32`
- `GF_SECURITY_ADMIN_PASSWORD` — Grafana admin password
- `LLM_API_KEY` — your LLM provider API key

### 3. Start services

```bash
docker compose up -d
```

This starts 7 services: app, PostgreSQL (with pgvector), Redis, OTEL collector, Jaeger, Prometheus, and Grafana.

### 4. Verify

```bash
# Health check
curl http://localhost:3000/health
# Expected: "OK"

# ApollosAI endpoint
curl http://localhost:3000/apollosai
# Expected: {"apollosai":true}

# Grafana (default: admin / your GF_SECURITY_ADMIN_PASSWORD)
open http://localhost:3001
```

### Development overrides

For local development with hot-reload and exposed debug ports:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

The dev override exposes PostgreSQL (5432), Redis (6379), and OTEL (4317/4318) ports on the host and mounts source code for live reload.

---

## Kubernetes — Helm

### 1. Create namespace and secrets

```bash
kubectl create namespace apollosai

# Create the secret with required values
kubectl create secret generic apollosai-secrets \
  --namespace apollosai \
  --from-literal=DATABASE_URL='postgresql+asyncpg://apollosai:PASSWORD@postgres:5432/apollosai' \
  --from-literal=REDIS_URL='redis://:PASSWORD@redis:6379/0' \
  --from-literal=REDIS_PASSWORD='PASSWORD' \
  --from-literal=POSTGRES_PASSWORD='PASSWORD' \
  --from-literal=JWT_SECRET="$(openssl rand -hex 32)" \
  --from-literal=SESSION_SECRET="$(openssl rand -hex 32)" \
  --from-literal=APOLLOSAI_ENCRYPTION_KEY="$(openssl rand -hex 32)" \
  --from-literal=LLM_API_KEY='your-api-key'
```

### 2. Install chart

```bash
# Development
helm install apollosai deploy/helm/apollosai \
  --namespace apollosai \
  -f deploy/helm/apollosai/values-dev.yaml \
  --set existingSecret=apollosai-secrets

# Production
helm install apollosai deploy/helm/apollosai \
  --namespace apollosai \
  -f deploy/helm/apollosai/values-prod.yaml \
  --set existingSecret=apollosai-secrets
```

### 3. Verify

```bash
kubectl get pods -n apollosai
kubectl logs -n apollosai -l app.kubernetes.io/name=apollosai --tail=50
kubectl port-forward -n apollosai svc/apollosai 3000:3000
curl http://localhost:3000/health
```

---

## Kubernetes — Kustomize

### 1. Create secrets file

```bash
cd deploy/k8s/base
cat > .env <<EOF
DATABASE_URL=postgresql+asyncpg://apollosai:PASSWORD@apollosai-postgresql:5432/apollosai
REDIS_URL=redis://:PASSWORD@apollosai-redis:6379/0
REDIS_PASSWORD=PASSWORD
POSTGRES_PASSWORD=PASSWORD
JWT_SECRET=$(openssl rand -hex 32)
SESSION_SECRET=$(openssl rand -hex 32)
APOLLOSAI_ENCRYPTION_KEY=$(openssl rand -hex 32)
LLM_API_KEY=your-api-key
EOF
```

The `.env` file is consumed by the `secretGenerator` in `kustomization.yaml`. It is gitignored.

### 2. Run migrations first

The migration job must complete before the app deployment starts. Three approaches:

**Manual (recommended for first deploy):**
```bash
kubectl apply -k deploy/k8s/overlays/dev    # or prod
kubectl wait --for=condition=complete job/apollosai-migration -n apollosai --timeout=120s
```

**Init container:** Add an init container to the app Deployment that runs migrations before the main container starts.

**ArgoCD sync-wave:** Add `argocd.argoproj.io/sync-wave: "-1"` to the migration Job metadata.

### 3. Apply overlay

```bash
# Development
kubectl apply -k deploy/k8s/overlays/dev

# Production
kubectl apply -k deploy/k8s/overlays/prod
```

### 4. Verify

```bash
kubectl get all -n apollosai
kubectl port-forward -n apollosai svc/apollosai 3000:3000
curl http://localhost:3000/health
```

---

## First-Time Setup

### Run database migrations

**Docker Compose:** Migrations run automatically on app startup via Alembic.

**Helm:** The migration Job runs as a `pre-install`/`pre-upgrade` hook automatically.

**Kustomize:** Apply the migration Job manually (see above).

### Create initial admin user

After the app is running and migrations are complete:

```bash
# Docker Compose
docker compose exec app python -m apollosai.cli create-admin --email admin@example.com

# Kubernetes
kubectl exec -n apollosai deploy/apollosai -- python -m apollosai.cli create-admin --email admin@example.com
```

---

## TLS Configuration

### Helm — Ingress TLS

Enable ingress with TLS in your values file:

```yaml
ingress:
  enabled: true
  className: nginx
  hosts:
    - host: apollosai.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: apollosai-tls
      hosts:
        - apollosai.example.com
```

### cert-manager integration

Install cert-manager and add an annotation to your ingress:

```yaml
ingress:
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
```

cert-manager will automatically provision and renew TLS certificates.

### Docker Compose

Use a reverse proxy (Traefik, Caddy, or nginx) in front of the app service for TLS termination. The app listens on port 3000 (HTTP only).

---

## Upgrading

### Docker Compose

```bash
cd deploy/docker-compose
docker compose pull
docker compose up -d
```

Migrations run automatically on startup.

### Helm

```bash
helm upgrade apollosai deploy/helm/apollosai \
  --namespace apollosai \
  -f deploy/helm/apollosai/values-prod.yaml \
  --set existingSecret=apollosai-secrets
```

The migration Job runs automatically as a `pre-upgrade` hook.

### Kustomize

```bash
# Update image tag in deployment.yaml, then:
kubectl apply -k deploy/k8s/overlays/prod

# Run migration job manually if schema changed
kubectl delete job apollosai-migration -n apollosai --ignore-not-found
kubectl apply -k deploy/k8s/overlays/prod
kubectl wait --for=condition=complete job/apollosai-migration -n apollosai --timeout=120s
```

---

## Security Considerations

### Docker socket access

The app container mounts `/var/run/docker.sock` to create and manage sandbox containers for AI agent execution. This grants **root-equivalent access to the host**.

**Mitigations:**
- **Rootless Docker** — Run the Docker daemon in rootless mode to limit the blast radius of container escapes.
- **Sysbox runtime** — Use Sysbox for nested container isolation without host Docker socket access.
- **K8s socket proxy** — In Kubernetes, use a DaemonSet-based Docker socket proxy that restricts API calls to only container creation/deletion.
- **Network policies** — Restrict which pods can communicate with the Docker socket proxy.

### Redis authentication

Redis must always run with `--requirepass`. The default Docker Compose and Helm configurations enforce this. Never expose Redis without authentication, even on internal networks.

### Default passwords

All `CHANGE_ME_BEFORE_PRODUCTION` values in `.env.example` **must** be replaced before any non-local deployment:
- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `JWT_SECRET` (min 32 characters)
- `SESSION_SECRET` (min 32 characters)
- `APOLLOSAI_ENCRYPTION_KEY`
- `GF_SECURITY_ADMIN_PASSWORD`

### Container image pinning

All Docker Compose and Helm configurations pin images to specific versions (e.g., `pgvector/pgvector:0.8.1-pg18`, `redis:8-alpine`). Do **not** use `:latest` tags in production. See the [Operational Runbook](runbook.md#image-version-management) for update procedures.

### Network isolation

In the Docker Compose stack, only the app (3000) and Grafana (3001) ports are exposed to the host by default. PostgreSQL, Redis, OTEL collector, Jaeger, and Prometheus are on an internal Docker network only. The dev override (`docker-compose.dev.yml`) exposes additional ports for local debugging.
