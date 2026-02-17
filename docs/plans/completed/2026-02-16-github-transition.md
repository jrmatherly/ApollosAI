# GitHub Configuration Transition Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transition all `.github/` configuration from OpenHands defaults to ApollosAI — fixing broken CI, disabling unused workflows, and rebranding templates.

**Architecture:** Bulk find-and-replace for runners/actions across 12 workflow files, targeted edits for broken references, disable 3 unused workflows, rebrand community-facing templates. All changes are config/YAML — no application code changes.

**Tech Stack:** GitHub Actions YAML, Bash shell script, GitHub issue/PR templates

**Source Document:** `.scratchpad/github-transition-plan.md` (full analysis with line-by-line findings)

---

## Task 1: Replace Blacksmith Runners with GitHub-Hosted Runners

**Files (12 workflows):**
- Modify: `.github/workflows/lint.yml`
- Modify: `.github/workflows/lint-fix.yml`
- Modify: `.github/workflows/py-tests.yml`
- Modify: `.github/workflows/fe-unit-tests.yml`
- Modify: `.github/workflows/fe-e2e-tests.yml`
- Modify: `.github/workflows/ghcr-build.yml`
- Modify: `.github/workflows/npm-publish-ui.yml`
- Modify: `.github/workflows/ui-build.yml`
- Modify: `.github/workflows/stale.yml`
- Modify: `.github/workflows/pr-review-by-apollos.yml`
- Modify: `.github/workflows/enterprise-preview.yml`
- Modify: `.github/workflows/pypi-release.yml`

**Step 1: Replace all Blacksmith runners**

Apply these replacements across all `.github/workflows/*.yml` files:

| Find | Replace |
|------|---------|
| `blacksmith-4vcpu-ubuntu-2204` | `ubuntu-22.04` |
| `blacksmith-4vcpu-ubuntu-2404` | `ubuntu-24.04` |
| `blacksmith-8vcpu-ubuntu-2204` | `ubuntu-22.04` |
| `runs-on: blacksmith` (bare) | `runs-on: ubuntu-latest` |

**Step 2: Verify no Blacksmith runners remain**

Run: `grep -r "blacksmith" .github/workflows/`
Expected: No output (0 matches)

**Step 3: Replace all Blacksmith actions**

Apply these replacements across all `.github/workflows/*.yml` files:

| Find | Replace |
|------|---------|
| `useblacksmith/setup-node@v5` | `actions/setup-node@v4` |
| `useblacksmith/setup-python@v6` | `actions/setup-python@v5` |
| `useblacksmith/build-push-action@v1` | `docker/build-push-action@v6` |

**Step 4: Verify no Blacksmith actions remain**

Run: `grep -r "useblacksmith" .github/workflows/`
Expected: No output (0 matches)

**Step 5: Commit**

```bash
git add .github/workflows/
git commit -m "ci: replace Blacksmith runners and actions with GitHub-hosted equivalents"
```

---

## Task 2: Fix Non-Existent Action Versions

**Files (4 workflows):**
- Modify: `.github/workflows/e2e-tests.yml` (line 22 for checkout@v4 already correct; lines 30, 41 for setup-python@v6 and setup-node@v6)
- Modify: `.github/workflows/apollos-resolver.yml` (line 92)
- Modify: `.github/workflows/pr-review-by-apollos.yml` (lines 52, 58, 70)
- Modify: `.github/workflows/check-package-versions.yml` (line 18)

**Context:** These workflows were partially rebranded but use action versions that don't exist yet (`actions/checkout@v5`, `actions/setup-python@v6`, `actions/setup-node@v6`). They will fail with "Unable to resolve action" errors.

**Step 1: Replace non-existent action versions**

Apply these replacements across all `.github/workflows/*.yml` files:

| Find | Replace |
|------|---------|
| `actions/checkout@v5` | `actions/checkout@v4` |
| `actions/setup-python@v6` | `actions/setup-python@v5` |
| `actions/setup-node@v6` | `actions/setup-node@v4` |

**Step 2: Verify no non-existent versions remain**

Run: `grep -rE "actions/(checkout@v5|setup-python@v6|setup-node@v6)" .github/workflows/`
Expected: No output (0 matches)

**Step 3: Verify correct versions are in place**

Run: `grep -rE "actions/(checkout@v4|setup-python@v5|setup-node@v4)" .github/workflows/`
Expected: Multiple matches across the 4 files

**Step 4: Commit**

```bash
git add .github/workflows/
git commit -m "ci: fix non-existent action versions (checkout@v5, setup-python@v6, setup-node@v6)"
```

---

## Task 3: Disable Publishing Workflows

**Files:**
- Modify: `.github/workflows/pypi-release.yml`
- Modify: `.github/workflows/npm-publish-ui.yml`

**Context:** Not publishing to PyPI or npm. Disable by removing triggers (keeping file for reference).

**Step 1: Disable pypi-release.yml**

The actual file has both `workflow_dispatch` (with inputs, lines 5-13) and `push: tags` (lines 14-16). Remove only the `push` trigger while preserving the existing `workflow_dispatch` block.

In `.github/workflows/pypi-release.yml`, remove the `push:` trigger section (lines 14-16):
```yaml
  push:
    tags:
      - '*'
```

And add a comment above the `on:` block:
```yaml
# DISABLED auto-trigger: Not publishing to PyPI. Manual dispatch still available.
```

**Step 2: Disable npm-publish-ui.yml**

In `.github/workflows/npm-publish-ui.yml`, change:
```yaml
on:
  push:
    branches:
      - main
    paths:
      - "openhands-ui/**"
      - ".github/workflows/npm-publish-ui.yml"
```
to:
```yaml
# DISABLED: Not publishing to npm. Re-enable triggers when needed.
on:
  workflow_dispatch:
```

**Step 3: Verify neither workflow has auto-triggers**

Run: `grep -A5 "^on:" .github/workflows/pypi-release.yml .github/workflows/npm-publish-ui.yml`
Expected: Both show only `workflow_dispatch:` under `on:`

**Step 4: Commit**

```bash
git add .github/workflows/pypi-release.yml .github/workflows/npm-publish-ui.yml
git commit -m "ci: disable pypi-release and npm-publish-ui workflows (not publishing)"
```

---

## Task 4: Disable Enterprise Preview Workflows

**Files:**
- Modify: `.github/workflows/enterprise-preview.yml`
- Modify: `.github/workflows/ghcr-build.yml` (enterprise-preview job, line ~243)

**Context:** The standalone `enterprise-preview.yml` dispatches to `OpenHands/deploy` (not our repo). The embedded job in `ghcr-build.yml` dispatches to a `deploy.yaml` that doesn't exist yet — its `curl --fail-with-body` will error and break the pipeline when a PR has the `deploy` label.

**SECURITY NOTE:** The `enterprise-preview.yml` sends `APOLLOS_BOT_GITHUB_PAT` to `OpenHands/deploy`. After disabling, rotate or scope the PAT to `jrmatherly/*` repos only. Verify the PAT does not grant access to `OpenHands/deploy`.

**Step 1: Disable enterprise-preview.yml**

In `.github/workflows/enterprise-preview.yml`, change:
```yaml
on:
  pull_request:
    types: [labeled]
```
to:
```yaml
# DISABLED: No deployment pipeline configured yet. The dispatch URL pointed
# to OpenHands/deploy which is not our repo.
on:
  workflow_dispatch:
```

**Step 2: Guard the embedded enterprise-preview job in ghcr-build.yml**

In `.github/workflows/ghcr-build.yml`, find the `enterprise-preview` job (around line 243). Change:
```yaml
  enterprise-preview:
    name: Enterprise preview
    if: github.event_name == 'pull_request' && contains(github.event.pull_request.labels.*.name, 'deploy')
```
to:
```yaml
  enterprise-preview:
    name: Enterprise preview
    # DISABLED: deploy.yaml workflow does not exist yet. Re-enable when deployment pipeline is ready.
    if: false && github.event_name == 'pull_request' && contains(github.event.pull_request.labels.*.name, 'deploy')
```

**Step 3: Verify both are disabled**

Run: `grep -A2 "enterprise-preview:" .github/workflows/ghcr-build.yml`
Expected: Shows `if: false &&`

Run: `grep -A2 "^on:" .github/workflows/enterprise-preview.yml`
Expected: Shows `workflow_dispatch:`

**Step 4: Commit**

```bash
git add .github/workflows/enterprise-preview.yml .github/workflows/ghcr-build.yml
git commit -m "ci: disable enterprise-preview workflows (no deploy pipeline configured)"
```

---

## Task 5: Fix stale.yml Repository Condition

**Files:**
- Modify: `.github/workflows/stale.yml` (line 12)

**Context:** The `if:` condition checks for `OpenHands/OpenHands`, meaning this workflow never runs on our fork.

**Step 1: Fix the repository condition**

In `.github/workflows/stale.yml`, change:
```yaml
    if: github.repository == 'OpenHands/OpenHands'
```
to:
```yaml
    if: github.repository_owner == 'jrmatherly'
```

**Step 2: Verify**

Run: `grep "github.repository" .github/workflows/stale.yml`
Expected: `if: github.repository == 'jrmatherly/ApollosAI'`

**Step 3: Commit**

```bash
git add .github/workflows/stale.yml
git commit -m "ci: fix stale.yml repository condition for ApollosAI"
```

---

## Task 6: Fix lint-fix.yml Git Identity

**Files:**
- Modify: `.github/workflows/lint-fix.yml` (lines 51-52, 93-94)

**Context:** The auto-fix workflow commits with `openhands@all-hands.dev` / `OpenHands Bot` identity.

**Step 1: Replace git identity (2 occurrences)**

In `.github/workflows/lint-fix.yml`, replace both occurrences of:
```yaml
          git config --local user.email "openhands@all-hands.dev"
          git config --local user.name "OpenHands Bot"
```
with:
```yaml
          git config --local user.email "bot@apollosai.dev"
          git config --local user.name "ApollosAI Bot"
```

**Step 2: Verify no OpenHands identity remains**

Run: `grep -n "openhands@\|OpenHands Bot" .github/workflows/lint-fix.yml`
Expected: No output (0 matches)

**Step 3: Commit**

```bash
git add .github/workflows/lint-fix.yml
git commit -m "ci: update lint-fix git identity to ApollosAI Bot"
```

---

## Task 7: Fix update_pr_description.sh Docker URLs

**Files:**
- Modify: `.github/scripts/update_pr_description.sh` (lines 16-18)

**Context:** Script references `docker.openhands.dev/openhands/*` which is OpenHands' Docker registry.

**Step 1: Replace Docker image references**

In `.github/scripts/update_pr_description.sh`, change:
```bash
  -e SANDBOX_RUNTIME_CONTAINER_IMAGE=docker.openhands.dev/openhands/runtime:${SHORT_SHA}-nikolaik \
  --name openhands-app-${SHORT_SHA} \
  docker.openhands.dev/openhands/openhands:${SHORT_SHA}"
```
to:
```bash
  -e SANDBOX_RUNTIME_CONTAINER_IMAGE=ghcr.io/${{ github.repository_owner }}/runtime:${SHORT_SHA}-nikolaik \
  --name apollos-app-${SHORT_SHA} \
  ghcr.io/${{ github.repository_owner }}/apollos:${SHORT_SHA}"
```

**Step 2: Verify no OpenHands Docker refs remain**

Run: `grep "docker.openhands.dev\|openhands-app" .github/scripts/update_pr_description.sh`
Expected: No output (0 matches)

**Step 3: Commit**

```bash
git add .github/scripts/update_pr_description.sh
git commit -m "ci: update PR description script Docker URLs to GHCR"
```

---

## Task 8: Fix dependabot.yml

**Files:**
- Modify: `.github/dependabot.yml` (lines 49-69)

**Context:** The `/docs` npm ecosystem entry has no `package.json` — only a `plans/` subdirectory. Dependabot will error on this entry.

**Step 1: Remove the /docs npm ecosystem entry**

In `.github/dependabot.yml`, remove this entire block (lines 49-69):
```yaml
  - package-ecosystem: "npm"
    directory: "/docs"
    schedule:
      interval: "weekly"
      day: "wednesday"
    open-pull-requests-limit: 1
    groups:
      docusaurus:
        patterns:
          - "*docusaurus*"
      eslint:
        patterns:
          - "*eslint*"
      security-all:
        applies-to: "security-updates"
        patterns:
          - "*"
      version-all:
        applies-to: "version-updates"
        patterns:
          - "*"
```

**Step 2: Verify no /docs reference remains**

Run: `grep "/docs" .github/dependabot.yml`
Expected: No output (0 matches)

**Step 3: Commit**

```bash
git add .github/dependabot.yml
git commit -m "ci: remove /docs npm entry from dependabot (no package.json)"
```

---

## Task 9: Rebrand Issue Templates

**Files:**
- Modify: `.github/ISSUE_TEMPLATE/bug_template.yml`
- Modify: `.github/ISSUE_TEMPLATE/feature_request.yml`

**Step 1: Rebrand bug_template.yml**

Apply these replacements in `.github/ISSUE_TEMPLATE/bug_template.yml`:

| Line | Find | Replace |
|------|------|---------|
| 2 | `Report a problem with OpenHands` | `Report a problem with ApollosAI` |
| 28 | `OpenHands crashes after` | `ApollosAI crashes after` |
| 37 | `OpenHands should execute` | `ApollosAI should execute` |
| 56 | `Install OpenHands using Docker` | `Install ApollosAI using Docker` |
| 58 | `` `openhands run` `` | `` `apollosai run` `` |
| 67 | `OpenHands Installation Method` | `ApollosAI Installation Method` |
| 68 | `How are you running OpenHands?` | `How are you running ApollosAI?` |
| 74 | `OpenHands Cloud (app.all-hands.dev)` | **Remove this line entirely** |
| 92 | `OpenHands Version` | `ApollosAI Version` |
| 93 | `` `openhands --version` `` | `` `apollosai --version` `` |
| 104 | `LATEST version of OpenHands` | `LATEST version of ApollosAI` |
| 158 | `In the OpenHands chat UI` | `In the ApollosAI chat UI` |

**Step 2: Rebrand feature_request.yml**

Apply these replacements in `.github/ISSUE_TEMPLATE/feature_request.yml`:

| Line | Find | Replace |
|------|------|---------|
| 2 | `Suggest a new feature or improvement for OpenHands` | `Suggest a new feature or improvement for ApollosAI` |
| 78 | `Which part of OpenHands does this feature relate to?` | `Which part of ApollosAI does this feature relate to?` |

**Step 3: Verify no OpenHands references remain in templates**

Run: `grep -i "openhands\|all-hands" .github/ISSUE_TEMPLATE/*.yml`
Expected: No output (0 matches)

**Step 4: Commit**

```bash
git add .github/ISSUE_TEMPLATE/
git commit -m "ci: rebrand issue templates from OpenHands to ApollosAI"
```

---

## Task 10: Rebrand welcome-good-first-issue.yml

**Files:**
- Modify: `.github/workflows/welcome-good-first-issue.yml` (lines 45, 48)

**Step 1: Replace OpenHands project reference**

In `.github/workflows/welcome-good-first-issue.yml`, change line 45:
```javascript
"This issue has been labeled as **good first issue**, which means it's a great place to get started with the OpenHands project.\n\n" +
```
to:
```javascript
"This issue has been labeled as **good first issue**, which means it's a great place to get started with the ApollosAI project.\n\n" +
```

**Step 2: Replace Slack links**

Change line 48:
```javascript
"Feel free to join our developer community on [Slack](https://openhands.dev/joinslack). You can ask for [help](https://openhands-ai.slack.com/archives/C078L0FUGUX), [feedback](https://openhands-ai.slack.com/archives/C086ARSNMGA), and even ask for a [PR review](https://openhands-ai.slack.com/archives/C08D8FJ5771).\n\n" +
```
to:
```javascript
"Feel free to check out our [development setup guide](" + repoUrl + "/blob/main/Development.md) to get started.\n\n" +
```

Note: This removes the Slack links since we don't have our own Slack workspace yet. The development guide link is already present on line 47 but this replaces the stale Slack references with a useful duplicate pointer.

**Step 3: Verify no OpenHands/Slack references remain**

Run: `grep -i "openhands\|slack" .github/workflows/welcome-good-first-issue.yml`
Expected: No output (0 matches)

**Step 4: Commit**

```bash
git add .github/workflows/welcome-good-first-issue.yml
git commit -m "ci: rebrand good-first-issue welcome message for ApollosAI"
```

---

## Task 11: Fix pr-review-by-apollos.yml

**Files:**
- Modify: `.github/workflows/pr-review-by-apollos.yml` (lines 10, 28, 35, 41-42)

**Context:** This workflow still references `all-hands-bot` and uses OpenHands' internal LLM proxy.

> **CRITICAL — ACTIVE SECRET LEAK:** The `LLM_BASE_URL` currently sends `LLM_API_KEY` to `https://llm-proxy.app.all-hands.dev` (OpenHands' infrastructure) on every PR review. Fix this immediately or disable the workflow until fixed.
>
> **CRITICAL — UNTRUSTED CODE EXECUTION:** This workflow uses `pull_request_target` and `cd`s into untrusted PR code before running a script with secrets (`LLM_API_KEY`, `APOLLOS_BOT_GITHUB_PAT`, `LMNR_PROJECT_API_KEY`). A malicious PR could exfiltrate all three secrets via import hooks or modified `pyproject.toml`. Consider: (a) passing the diff via stdin instead of `cd`-ing into the PR repo, (b) using `pull_request` trigger instead, or (c) running the agent in a separate job without PR checkout.

**Step 1: Remove all-hands-bot reviewer trigger**

In `.github/workflows/pr-review-by-apollos.yml`:

Change the comment on line 10 from:
```yaml
    #   4. A maintainer requests apollos-agent or all-hands-bot as a reviewer
```
to:
```yaml
    #   4. A maintainer requests apollos-agent as a reviewer
```

Change the comment on line 28 from:
```yaml
        #   4. apollos-agent or all-hands-bot is requested as a reviewer
```
to:
```yaml
        #   4. apollos-agent is requested as a reviewer
```

Remove line 35 entirely:
```yaml
            github.event.requested_reviewer.login == 'all-hands-bot'
```

**Step 2: Fix LLM configuration**

Change lines 41-42 from:
```yaml
            LLM_MODEL: litellm_proxy/claude-sonnet-4-5-20250929
            LLM_BASE_URL: https://llm-proxy.app.all-hands.dev
```
to:
```yaml
            LLM_MODEL: anthropic/claude-sonnet-4-5-20250929
            # LLM_BASE_URL: Set via secrets if using a custom LLM proxy
```

**Step 3: Verify no OpenHands references remain**

Run: `grep -i "all-hands\|openhands" .github/workflows/pr-review-by-apollos.yml`
Expected: No output (0 matches)

**Step 4: Commit**

```bash
git add .github/workflows/pr-review-by-apollos.yml
git commit -m "ci: remove all-hands-bot and OpenHands LLM proxy from PR review workflow"
```

---

## Task 12: Final Validation Sweep

**Step 1: Check for any remaining OpenHands/all-hands references**

Run: `grep -ri "openhands\|all-hands\|all_hands" .github/ --include="*.yml" --include="*.yaml" --include="*.sh" --include="*.md"`
Expected: Only matches in files tied to the Python package rename (e.g., `--cov=openhands` in `py-tests.yml`, `openhands-ui/` paths in `ui-build.yml`). These are deferred until the package rename.

**Step 2: Check for any remaining Blacksmith references**

Run: `grep -ri "blacksmith\|useblacksmith" .github/`
Expected: No output (0 matches)

**Step 3: Check for non-existent action versions**

Run: `grep -rE "actions/(checkout@v5|setup-python@v6|setup-node@v6)" .github/`
Expected: No output (0 matches)

**Step 4: Validate YAML syntax on all workflow files**

Run: `python3 -c "import yaml, glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]; print('All YAML valid')"`
Expected: `All YAML valid`

**Step 5: Review the full diff**

Run: `git diff --stat`
Expected: Changes across ~18 files in `.github/`

**Step 6: Final commit (if any stragglers)**

Only if validation revealed fixes:
```bash
git add .github/
git commit -m "ci: fix validation issues from GitHub transition"
```

---

## Deferred Items (Not Part of This Plan)

These items are tracked in `.scratchpad/github-transition-plan.md` and depend on the Python package rename (`openhands` → `apollos`):

- `py-tests.yml` — `--cov=openhands` and `coverage-openhands` artifact name
- `ui-build.yml` — `openhands-ui/` path references
- `ghcr-build.yml` — `apollos.runtime.utils` module reference
- `apollos-resolver.yml` — `apollos.resolver.*` module references
- `e2e-tests.yml` — `apollos.server`, `apollos.resolver` module references
- `pr-review-by-apollos.yml` — verify `jrmatherly/software-agent-sdk` repo exists

---

## Fork Maintenance Strategy

**Upstream tracking**: Maintain an `upstream/main` remote pointing to `OpenHands/OpenHands`.

**Merge frequency**: Weekly merge from upstream to catch breaking changes early. Use `git merge upstream/main` with manual conflict resolution.

**Workflow file conflicts**: `.github/workflows/` files will frequently conflict during upstream merges. Use `git checkout --ours .github/workflows/` for files we've customized, then manually review any new upstream workflows.

**Recommended `.gitattributes`**:
```
.github/workflows/*.yml merge=ours
```
This prevents upstream workflow changes from overwriting our customizations during merges. New workflows from upstream will still appear as untracked files.
