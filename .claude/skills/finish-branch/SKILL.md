---
name: finish-branch
description: Merge a PR and clean up the associated worktree and branch
disable-model-invocation: true
---

Merge a PR and clean up the worktree/branch. Takes a PR number as argument (e.g., `/finish-branch 7`).

If no PR number is provided, detect the current branch and find its open PR.

## Steps

1. **Identify the PR and branch**:
   ```bash
   gh pr view <number> --json headRefName,state,mergeable,mergeStateStatus,statusCheckRollup
   ```
   - If PR is not OPEN, report and stop
   - If not MERGEABLE or checks are failing, report which checks failed and stop

2. **Find the worktree** (if any):
   ```bash
   git worktree list
   ```
   Match the branch name to a worktree path.

3. **Run tests in the worktree** (if one exists):
   ```bash
   cd <worktree-path> && poetry run pytest tests/unit/apollosai/ -q
   ```
   If tests fail, report and stop.

4. **Merge the PR** — do NOT use `--delete-branch` (it fails when a worktree holds the branch):
   ```bash
   gh pr merge <number> --squash
   ```
   This MUST run from the main repo directory (`/Users/jason/dev/ApollosAI`), NOT from a worktree.

5. **Remove the worktree** (must happen BEFORE branch deletion):
   ```bash
   git worktree remove <worktree-path>
   ```

6. **Delete the local branch**:
   ```bash
   git branch -d <branch-name>
   ```

7. **Pull main**:
   ```bash
   git pull origin main
   ```

8. **Report**: Show the merge commit and confirm cleanup is complete.

## Rules

- MUST remove worktree BEFORE deleting local branch — git refuses to delete a branch held by a worktree
- Do NOT use `--delete-branch` with `gh pr merge` when a worktree exists for the branch
- `gh pr merge` MUST run from the main repo directory, NOT from a worktree (fails with "'main' is already used by worktree")
- Always verify tests pass before merging
- Always pull main after merge to fast-forward
- If the remote branch wasn't auto-deleted by GitHub, clean it up: `git push origin --delete <branch>`
