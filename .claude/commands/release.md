---
description: "Create a release: version bump, changelog, PR, tag, and GitHub Release (need gh command)"
argument-hint: "[tag=vX.Y.Z] [rev=COMMIT]"
allowed-tools:
  - "Bash(git:*)"
  - "Bash(gh:*)"
  - "Bash(PYTHONPATH=src uv run:*)"
  - "Bash(UV_CACHE_DIR=.uv-cache uv run:*)"
  - Read
  - Edit
  - Grep
  - Glob
---

Create a release for this project.
User arguments: $ARGUMENTS

## Argument Parsing

Parse `$ARGUMENTS` for optional key=value pairs:
- `tag=vX.Y.Z` — the release tag (e.g. `tag=v1.0.0b2`). Strip the `v` prefix when used as a version string in code.
- `rev=COMMIT` — the target revision (commit SHA or ref). Default: HEAD of the default branch.

If neither is provided, follow the interactive flow in Phase 1.

## Project Context

Adapt ALL steps below to these project-specific settings.
When reusing this command for another project, update this section AND the allowed-tools in the frontmatter.

- **Language/Tooling**: Python, uv, ruff, pytest
- **Version file**: `src/helix/__init__.py` (`__version__` variable)
- **Versioning scheme**: PEP 440 (e.g. `1.0.0`, `1.0.0b1`, `1.0.0rc1`)
- **Changelog**: `CHANGELOG.md` (Keep a Changelog format)
- **Commit convention**: Conventional Commits (feat/fix/improve/chore/docs/test/perf)
- **Default branch**: main (protected — direct push blocked, must use PR)
- **Merge strategy**: `--squash` preferred. Fallback: `--rebase`. NEVER `--merge`.
- **Release workflow**: `.github/workflows/release.yml` (tag push → CI → build → publish → release)
- **Publishing target**: PyPI via Trusted Publishing
- **Lint command**: `UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check .`
- **Test command**: `PYTHONPATH=src uv run --no-editable python -m pytest -q`
- **Pre-release indicator**: version contains `a`, `b`, `rc`, or `dev`

## Pre-computed Context

Current version:
!`grep -m1 '__version__' src/helix/__init__.py`

Last tag:
!`git describe --tags --abbrev=0 2>/dev/null || echo "(no tags)"`

Commits since last tag:
!`git log $(git describe --tags --abbrev=0 2>/dev/null || echo HEAD~10)..HEAD --oneline`

## Steps

### Phase 0: Preflight

1. Run `gh auth status` to verify authentication. If not authenticated, tell the user to run `gh auth login` and stop immediately.

### Phase 1: Determine Tag and Revision

2. If `rev=` is NOT specified, use HEAD of the default branch.
3. If `tag=` is NOT specified:
   a. Read the version file to get the current version.
   b. Analyze commits since the last tag. Categorize by commit convention type.
   c. Propose 2-3 version candidates with reasoning based on the versioning scheme and changes found.
   d. Present the candidates to the user and wait for selection or custom input.
   e. The user's response becomes the tag. Ensure `v` prefix for git tags, strip `v` for version strings in code.

### Phase 2: Update Version and Changelog

4. Update the version file with the new version string (without `v` prefix).
5. Update the changelog:
   a. Create a new section below the unreleased header with the new version and today's date.
   b. Categorize commits into appropriate subsections (Added, Changed, Fixed, etc.).
   c. Update comparison URLs at the bottom of the file.

### Phase 3: Verify

6. Run the lint command. If it fails, fix the issue before proceeding.
7. Run the test command. If it fails, fix the issue before proceeding.

### Phase 4: Commit, PR, and Merge

8. Create a release branch: `git checkout -b release/<TAG>`
9. Stage and commit the changed files with message: `chore: bump version to <VERSION>` (same as /commit would do, but with this fixed message).
10. Push, create PR to the default branch, wait for CI, and squash-merge. Follow the same flow as /create-pr-with-merge: push unpushed commits, create PR with title `chore: release <TAG>`, wait for CI checks, then merge using the project's merge strategy. On CI failure or merge conflict, stop and report (do NOT force-merge, keep the PR open).

### Phase 5: Tag and Release

11. Sync local default branch: `git checkout <default-branch> && git pull --rebase origin <default-branch>`
12. Create an annotated tag: `git tag -a <TAG> -m "Release <TAG>"` on the target revision.
13. Push the tag: `git push origin <TAG>`
14. Monitor the release workflow: `gh run list --limit 1` then `gh run watch <RUN_ID>`
15. If the publish job fails but build succeeds, inform the user that publishing may not be configured. Proceed to step 16.
16. If the release job is skipped or fails, create a GitHub Release manually with `gh release create`. Add `--prerelease` flag if the version is a pre-release. Generate notes from the changelog section for this version.

### Phase 6: Report

17. Print a summary: release tag and version, GitHub Release URL, publish status (success / failed / skipped), and list of included changes.

## Error Handling

- **gh auth failure**: Tell the user to run `gh auth login` and stop.
- **Protected branch push rejected**: This is expected. Use the PR-based flow in Phase 4.
- **CI check failure**: Show the failing check and stop. Do NOT force-merge.
- **Tag already exists**: Inform the user and stop. Do NOT delete existing tags without explicit confirmation.
- **No changes since last tag**: Warn the user. Ask whether to proceed.
- **Merge conflict**: Show the conflict and stop. Do NOT auto-resolve.
