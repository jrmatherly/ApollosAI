# Unified Docker Image — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate the two-image Docker build (base `openhands` + enterprise overlay `apollosai`) into a single unified image that ships everything by default.

**Architecture:** The thin `containers/apollosai/Dockerfile` overlay adds three things to the base: `COPY apollosai/`, `ENV OPENHANDS_CONFIG_CLS`, and a different `CMD`. All three are merged directly into `containers/app/Dockerfile`. The `containers/apollosai/` directory is archived to `.scratchpad/backup/`. CI, Makefile, Docker Compose, and docs are updated to remove the two-image workflow.

**Tech Stack:** Docker multi-stage build, GitHub Actions, Docker Compose, Helm, Kustomize, bash

---

## Task 1: Merge enterprise additions into the unified Dockerfile

**Files:**
- Modify: `containers/app/Dockerfile:77-96` (final stage — add `apollosai/` COPY, ENV, change CMD)

**Step 1: Add `COPY apollosai/` after the plugins COPY**

In `containers/app/Dockerfile`, after line 78 (`COPY --chown=openhands:openhands --chmod=777 ./openhands/runtime/plugins ./openhands/runtime/plugins`), add:

```dockerfile
COPY --chown=openhands:openhands --chmod=770 ./apollosai ./apollosai
```

**Step 2: Add `ENV OPENHANDS_CONFIG_CLS` before ENTRYPOINT**

After `WORKDIR /app` (line 93) and before `ENTRYPOINT`, add:

```dockerfile
ENV OPENHANDS_CONFIG_CLS=apollosai.server.config.ApollosAIServerConfig
```

**Step 3: Change CMD to V1 enterprise server**

Replace line 96:
```dockerfile
# Before:
CMD ["uvicorn", "openhands.server.listen:app", "--host", "0.0.0.0", "--port", "3000"]

# After:
CMD ["uvicorn", "apollosai.app_server:app", "--host", "0.0.0.0", "--port", "3000"]
```

**Step 4: Remove the enterprise-server label (not applicable to unified image)**

The `LABEL org.apollosai.component="enterprise-server"` from the old overlay is NOT needed. The unified image is just "the app."

**Step 5: Commit**

```bash
git add containers/app/Dockerfile
git commit -m "feat(docker): merge apollosai into unified Dockerfile

Add COPY apollosai/, set OPENHANDS_CONFIG_CLS env, and change CMD
to boot the V1 enterprise server (apollosai.app_server:app) instead
of the legacy V0 server."
```

---

## Task 2: Update build.sh to route `-i apollosai` to `containers/app/`

**Files:**
- Modify: `containers/build.sh:80-86`

**Step 1: Extend the image name routing**

Replace lines 80-86 in `containers/build.sh`:

```bash
# Before:
if [[ "$image_name" == "openhands" ]]; then
  dir="./containers/app"
elif [[ "$image_name" == "runtime" ]]; then
  dir="./containers/runtime"
else
  dir="./containers/$image_name"
fi

# After:
if [[ "$image_name" == "openhands" || "$image_name" == "apollosai" ]]; then
  dir="./containers/app"
elif [[ "$image_name" == "runtime" ]]; then
  dir="./containers/runtime"
else
  dir="./containers/$image_name"
fi
```

This makes `build.sh -i apollosai` resolve to `containers/app/` (and its `config.sh` which sets `DOCKER_IMAGE=apollosai`), so `make docker-build-ent` continues to work.

**Step 2: Commit**

```bash
git add containers/build.sh
git commit -m "feat(docker): route -i apollosai to unified containers/app/"
```

---

## Task 3: Update Docker Compose to use unified Dockerfile

**Files:**
- Modify: `deploy/docker-compose/docker-compose.yml:27-30`
- Modify: `deploy/docker-compose/docker-compose.dev.yml:14-19`

**Step 1: Change the Dockerfile path in docker-compose.yml**

In `deploy/docker-compose/docker-compose.yml`, line 29:

```yaml
# Before:
      dockerfile: ./containers/apollosai/Dockerfile

# After:
      dockerfile: ./containers/app/Dockerfile
```

**Step 2: Update the header comment**

Replace lines 1-23 of docker-compose.yml:

```yaml
# Before (lines 7-11):
#   2. Build the app image locally (it is NOT available on a public registry):
#        docker compose build app
#      This requires the base image. Pull it once (or rebuild when deps change):
#        docker pull ghcr.io/jrmatherly/apollosai:latest   # OR
#        ./containers/build.sh -i openhands

# After:
#   2. Build the app image locally (it is NOT available on a public registry):
#        docker compose build app
```

Remove the lines about pulling the base image, since there's no longer a separate base.

**Step 3: Update docker-compose.dev.yml comment**

In `deploy/docker-compose/docker-compose.dev.yml`, replace lines 17-19:

```yaml
# Before:
      # Inherit dockerfile from main compose (containers/apollosai/Dockerfile).
      # DO NOT override to containers/app/Dockerfile — that builds the base
      # OpenHands image without the apollosai enterprise layer.

# After:
      # Inherit dockerfile from main compose (containers/app/Dockerfile).
```

**Step 4: Commit**

```bash
git add deploy/docker-compose/docker-compose.yml deploy/docker-compose/docker-compose.dev.yml
git commit -m "feat(docker): point docker-compose at unified containers/app/Dockerfile"
```

---

## Task 4: Consolidate Makefile Docker targets

**Files:**
- Modify: `Makefile:393-400` (docker-build targets)
- Modify: `Makefile:448-449` (help text)

**Step 1: Make docker-build-ent an alias**

Replace lines 393-400 in the Makefile:

```makefile
# Before:
# Docker builds
docker-build-app:
	@echo "$(YELLOW)Building ApollosAI app image...$(RESET)"
	@./containers/build.sh -i openhands --load

docker-build-ent:
	@echo "$(YELLOW)Building ApollosAI enterprise image...$(RESET)"
	@./containers/build.sh -i apollosai --load

# After:
# Docker builds (unified image — apollosai source is built into the app image)
docker-build-app:
	@echo "$(YELLOW)Building ApollosAI image...$(RESET)"
	@./containers/build.sh -i openhands --load

docker-build-ent: docker-build-app
	@echo "$(YELLOW)(docker-build-ent is now an alias for docker-build-app — single unified image)$(RESET)"
```

**Step 2: Update help text**

Replace lines 448-449:

```makefile
# Before:
	@echo "  $(GREEN)docker-build-app$(RESET)    - Build ApollosAI app Docker image"
	@echo "  $(GREEN)docker-build-ent$(RESET)    - Build ApollosAI enterprise Docker image"

# After:
	@echo "  $(GREEN)docker-build-app$(RESET)    - Build ApollosAI Docker image (unified)"
	@echo "  $(GREEN)docker-build-ent$(RESET)    - Alias for docker-build-app"
```

**Step 3: Commit**

```bash
git add Makefile
git commit -m "refactor(make): consolidate docker-build-ent into docker-build-app"
```

---

## Task 5: Disable the enterprise CI job in ghcr-build.yml

**Files:**
- Modify: `.github/workflows/ghcr-build.yml:180-249` (ghcr_build_enterprise job)

**Step 1: Add `if: false` and update the name/comment**

Replace lines 180-189:

```yaml
# Before:
  ghcr_build_enterprise:
    name: Push Enterprise Image
    runs-on: ubuntu-22.04
    permissions:
      contents: read
      packages: write
    needs: [define-matrix, ghcr_build_app]
    # Do not build enterprise in forks
    if: github.event.pull_request.head.repo.fork != true

# After:
  ghcr_build_enterprise:
    name: Push Enterprise Image (DISABLED — consolidated into ghcr_build_app)
    runs-on: ubuntu-22.04
    permissions:
      contents: read
      packages: write
    needs: [define-matrix, ghcr_build_app]
    # DISABLED: Enterprise code is now part of the unified containers/app/Dockerfile.
    # The ghcr_build_app job publishes to ghcr.io/jrmatherly/apollosai which
    # includes both openhands/ and apollosai/ source. Re-enable if a separate
    # enterprise image is ever needed again.
    if: false
```

Keep the rest of the job body (steps, metadata, build-push-action) intact for future reference.

**Step 2: Commit**

```bash
git add .github/workflows/ghcr-build.yml
git commit -m "ci: disable ghcr_build_enterprise job (consolidated into app build)"
```

---

## Task 6: Simplify docker-publish.yml to single image path

**Files:**
- Modify: `.github/workflows/docker-publish.yml:8-16,58-78`

**Step 1: Remove the openhands image choice**

Replace the `inputs.image` section (lines 8-16):

```yaml
# Before:
      image:
        description: "Image to build"
        required: true
        type: choice
        options:
          - apollosai
          - openhands
        default: apollosai

# After:
      image:
        description: "Image to build (unified)"
        required: true
        type: choice
        options:
          - apollosai
        default: apollosai
```

**Step 2: Simplify the image routing logic**

Replace the `Determine image and tags` step (lines 58-78):

```yaml
      - name: Determine image and tags
        id: meta
        run: |
          SHORT_SHA=$(git rev-parse --short HEAD)
          DOCKERFILE="containers/app/Dockerfile"
          IMAGE_REF="${REGISTRY}/${REPO_OWNER}/apollosai"
          TAGS="${IMAGE_REF}:sha-${SHORT_SHA}"

          echo "image_name=${INPUT_IMAGE}" >> "$GITHUB_OUTPUT"
          echo "dockerfile=${DOCKERFILE}" >> "$GITHUB_OUTPUT"
          echo "image_ref=${IMAGE_REF}" >> "$GITHUB_OUTPUT"
          echo "tags=${TAGS}" >> "$GITHUB_OUTPUT"
          echo "short_sha=${SHORT_SHA}" >> "$GITHUB_OUTPUT"
```

**Step 3: Commit**

```bash
git add .github/workflows/docker-publish.yml
git commit -m "ci: simplify docker-publish to single unified image path"
```

---

## Task 7: Update deployment documentation

**Files:**
- Modify: `deploy/docs/deployment-guide.md:21-35`
- Modify: `deploy/docs/runbook.md:90-96,237`

**Step 1: Simplify the build instructions in deployment-guide.md**

Replace lines 21-35 in `deploy/docs/deployment-guide.md`:

```markdown
### 1. Build the app image

The app image (`apollosai:latest`) is built locally — it is not available on a public registry:

\`\`\`bash
cd deploy/docker-compose
docker compose build app
\`\`\`

This performs a full multi-stage build: frontend compilation, Python dependency installation, and source code packaging into a single unified image.
```

Remove the "base image" language and the `docker pull` instructions (lines 23-35) since there's no longer a separate base image to pull.

**Step 2: Fix the rollback image reference in runbook.md**

Replace line 95 in `deploy/docs/runbook.md`:

```yaml
# Before:
    image: ghcr.io/jrmatherly/apollosai/enterprise-server:sha-abc1234

# After:
    image: ghcr.io/jrmatherly/apollosai:sha-abc1234
```

**Step 3: Fix the GHCR version check command in runbook.md**

Replace line 237 in `deploy/docs/runbook.md`:

```bash
# Before:
   gh api /users/jrmatherly/packages/container/apollosai%2Fenterprise-server/versions --jq '.[0:5] | .[].metadata.container.tags'

# After:
   gh api /users/jrmatherly/packages/container/apollosai/versions --jq '.[0:5] | .[].metadata.container.tags'
```

**Step 4: Commit**

```bash
git add deploy/docs/deployment-guide.md deploy/docs/runbook.md
git commit -m "docs: update deployment docs for unified Docker image"
```

---

## Task 8: Update CLAUDE.md references

**Files:**
- Modify: `CLAUDE.md` (two references to the enterprise image / old build flow)

**Step 1: Update the build commands section**

In the Build & Run section, change:

```markdown
# Before:
make docker-build-app         # Build ApollosAI app Docker image
make docker-build-ent         # Build ApollosAI enterprise Docker image

# After:
make docker-build-app         # Build ApollosAI Docker image (unified)
make docker-build-ent         # Alias for docker-build-app
```

**Step 2: Update the container builds note in Code Style**

Replace the line:

```markdown
# Before:
- Container builds: `containers/build.sh -i openhands` maps to `./containers/app/`; `-i apollosai` maps to `./containers/apollosai/` (enterprise image)

# After:
- Container builds: `containers/build.sh -i openhands` and `-i apollosai` both map to `./containers/app/` (single unified image)
```

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for unified Docker image"
```

---

## Task 9: Archive the old containers/apollosai/ directory

**Files:**
- Move: `containers/apollosai/` -> `.scratchpad/backup/containers-apollosai-archived/`

**Step 1: Create backup directory and move**

```bash
mkdir -p .scratchpad/backup
mv containers/apollosai .scratchpad/backup/containers-apollosai-archived
```

**Step 2: Verify no broken references**

Search for remaining references to the archived directory:

```bash
grep -r "containers/apollosai" --include="*.yml" --include="*.yaml" --include="*.sh" --include="*.md" --include="Makefile" .
```

Expected: No hits in active files (only in `.scratchpad/backup/` and git history).

**Step 3: Commit**

```bash
git add containers/apollosai .scratchpad/backup/containers-apollosai-archived
git commit -m "chore: archive containers/apollosai/ to .scratchpad/backup/

The enterprise overlay Dockerfile is no longer needed — all enterprise
code is now built into the unified containers/app/Dockerfile."
```

---

## Task 10: Verify the build works

**Step 1: Run the unified build locally**

```bash
make docker-build-app
```

Expected: Build completes successfully, image includes both `openhands/` and `apollosai/` source.

**Step 2: Verify the enterprise config ENV is baked in**

```bash
docker run --rm apollosai:latest env | grep OPENHANDS_CONFIG_CLS
```

Expected output:
```
OPENHANDS_CONFIG_CLS=apollosai.server.config.ApollosAIServerConfig
```

**Step 3: Verify the CMD boots the V1 server**

```bash
docker inspect apollosai:latest --format '{{json .Config.Cmd}}'
```

Expected output:
```json
["uvicorn","apollosai.app_server:app","--host","0.0.0.0","--port","3000"]
```

**Step 4: Run pre-commit on all modified files**

```bash
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml
```

Expected: All hooks pass. (No Python files were modified, but shell scripts and YAML may be linted.)

---

## Task 11: Update memory files

**Step 1: Update MEMORY.md**

Remove references to separate enterprise image and update relevant sections to reflect the unified image.

**Step 2: Commit any memory file changes (if applicable)**

This is a housekeeping step — not committed to the repo.
