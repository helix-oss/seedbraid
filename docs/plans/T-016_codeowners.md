# T-016: CODEOWNERS Definition -- Implementation Plan

## Overview and Goals

`.github/CODEOWNERS` file to enable GitHub automatic review request assignment.
Currently, no CODEOWNERS file exists, so security-critical file changes
(container.py, codec.py, etc.) can be merged without targeted review.

| Item | Value |
|------|-------|
| Priority | P2 |
| Category | Community |
| Size | S (1 file, ~45 lines) |
| Dependencies | None |
| Prerequisite | T-015 (completed -- community standards in place) |
| Estimated Time | 15 min |

### Goals

1. Enable automatic reviewer assignment on PRs based on file ownership rules
2. Enforce security review for cryptographic / integrity-critical modules
3. Route CI/DevOps changes to appropriate reviewers
4. Provide clear documentation within the file for future maintainers

---

## Affected Files and Components

| File | Action | Description |
|------|--------|-------------|
| `.github/CODEOWNERS` | **New** | Code ownership rules for GitHub automatic review requests |

### Related Existing Files (no modification required)

| File | Relationship |
|------|-------------|
| `.github/PULL_REQUEST_TEMPLATE.md` | PR template triggers review along with CODEOWNERS |
| `.github/workflows/ci.yml` | CI checks that run alongside reviews |
| `.github/ISSUE_TEMPLATE/` | Community standards (T-015, completed) |
| `SECURITY.md` | Security policy referenced by security-critical ownership |
| `CONTRIBUTING.md` | Contribution guidelines, references Code of Conduct |

---

## CODEOWNERS File Content (Proposed)

```
# Helix CODEOWNERS
# https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
#
# Rules are evaluated bottom-to-top; the LAST matching pattern takes precedence.
# When a PR modifies files matching a pattern below, the specified owners are
# automatically requested for review.
#
# NOTE: Replace placeholder team/user names with actual GitHub teams or usernames
# before merging. Teams must exist in the GitHub organization and have repository
# access for CODEOWNERS to function.

# ============================================================================
# Default: all files require maintainers review
# ============================================================================
*                                @helix-oss/maintainers

# ============================================================================
# Security-Critical Paths
# These modules handle binary format parsing, cryptographic operations,
# data integrity verification, and network transport. Changes require
# security-focused review.
# ============================================================================
src/helix/container.py           @helix-oss/security-reviewers
src/helix/codec.py               @helix-oss/security-reviewers
src/helix/ipfs.py                @helix-oss/security-reviewers
src/helix/storage.py             @helix-oss/security-reviewers
src/helix/pinning.py             @helix-oss/security-reviewers
src/helix/errors.py              @helix-oss/security-reviewers

# ============================================================================
# Specification & Security Documentation
# Format/design changes require both architecture and security sign-off.
# ============================================================================
docs/FORMAT.md                   @helix-oss/maintainers @helix-oss/security-reviewers
docs/THREAT_MODEL.md             @helix-oss/security-reviewers
SECURITY.md                      @helix-oss/security-reviewers

# ============================================================================
# CI / DevOps
# Workflow, build, and infrastructure changes require DevOps review.
# ============================================================================
.github/                         @helix-oss/devops
scripts/                         @helix-oss/devops
pyproject.toml                   @helix-oss/devops

# ============================================================================
# Test Suite
# Security-critical tests require security reviewer in addition to QA.
# General test changes are reviewed by QA.
# ============================================================================
tests/test_signature.py          @helix-oss/security-reviewers
tests/test_encryption.py         @helix-oss/security-reviewers
tests/test_container.py          @helix-oss/security-reviewers
tests/                           @helix-oss/qa

# ============================================================================
# Governance Documentation
# ============================================================================
CONTRIBUTING.md                  @helix-oss/maintainers
CODE_OF_CONDUCT.md               @helix-oss/maintainers
README.md                        @helix-oss/maintainers
```

---

## Step-by-Step Implementation Plan

### Step 1: Confirm GitHub Teams Exist (Pre-Implementation)

Before creating the file, verify or create the required GitHub teams in the
`helix-oss` organization:

| Team | Purpose | Minimum Members |
|------|---------|-----------------|
| `@helix-oss/maintainers` | Project leads, core developers | 1 |
| `@helix-oss/security-reviewers` | Crypto / integrity specialists | 1 |
| `@helix-oss/devops` | CI/CD, infrastructure | 1 |
| `@helix-oss/qa` | Test engineers, quality assurance | 1 |

If using individual usernames instead of teams (e.g., solo maintainer), replace
`@helix-oss/maintainers` with `@username` throughout the file.

**Note**: CODEOWNERS will fail silently if referenced teams/users do not exist
or lack repository access. GitHub shows a validation warning in the repository
Settings > Code review > CODEOWNERS errors section.

### Step 2: Create `.github/CODEOWNERS`

Create the file with the content from the "CODEOWNERS File Content" section above.

Key design decisions in the file:

1. **Bottom-to-top precedence**: GitHub uses the LAST matching pattern. More specific
   rules (security-critical paths, tests) are placed below the default `*` rule.
2. **Security-critical paths**: 6 modules (`container.py`, `codec.py`, `ipfs.py`,
   `storage.py`, `pinning.py`, `errors.py`) based on THREAT_MODEL.md scope.
3. **Dual ownership for FORMAT.md**: Both maintainers and security-reviewers are
   assigned since format changes impact security guarantees.
4. **Wildcard `tests/` for QA**: General test ownership with specific overrides
   for security-related test files above the wildcard rule.

### Step 3: Local Validation

Run the following checks before committing:

```bash
# 1. Verify file is in correct location
ls -la .github/CODEOWNERS

# 2. Verify no syntax errors (basic checks)
# - Each line should be: <pattern> <@owner1> [@owner2...]
# - No trailing whitespace issues
# - Comments start with #
cat -A .github/CODEOWNERS | head -60

# 3. Verify file is not empty
wc -l .github/CODEOWNERS
# Expected: ~55 lines

# 4. Run ruff (should not affect Python linting, but verify CI still passes)
UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check .

# 5. Run tests (no functional change expected)
PYTHONPATH=src uv run --no-editable python -m pytest
```

### Step 4: Commit with Conventional Prefix

```bash
git add .github/CODEOWNERS
git commit -m "docs: add CODEOWNERS for automatic review assignment (T-016)"
```

### Step 5: Post-Merge Verification on GitHub

After the commit is pushed/merged to `main`:

1. **GitHub UI validation**: Navigate to repository Settings > Code review > CODEOWNERS errors.
   Verify no errors are reported.

2. **Test PR verification** (create a test branch):

   | Test Case | File to Modify | Expected Reviewer |
   |-----------|---------------|-------------------|
   | Security path | `src/helix/container.py` | `@helix-oss/security-reviewers` |
   | Security path | `src/helix/codec.py` | `@helix-oss/security-reviewers` |
   | CI/DevOps path | `.github/workflows/ci.yml` | `@helix-oss/devops` |
   | Default path | `src/helix/cli.py` | `@helix-oss/maintainers` |
   | Spec path | `docs/FORMAT.md` | `@helix-oss/maintainers` + `@helix-oss/security-reviewers` |
   | Test path | `tests/test_container.py` | `@helix-oss/security-reviewers` |
   | General test | `tests/test_roundtrip.py` | `@helix-oss/qa` |

3. **Enforcement (optional)**: Enable "Require review from Code Owners" in branch
   protection rules (Settings > Branches > main > Require a pull request before merging
   > Require review from Code Owners).

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Teams do not exist in GitHub org | Medium | Validate team existence before merging; GitHub shows CODEOWNERS errors in Settings |
| Incorrect pattern matching (bottom-to-top precedence) | Low | Patterns ordered deliberately; verify with test PRs |
| Over-restrictive ownership blocks PRs | Low | Start with request-only (not required); enable enforcement gradually |
| IPFS test glob `tests/test_ipfs_*.py` may not match | Low | Removed glob pattern from proposal; IPFS tests fall under general `tests/` -> QA rule |
| Stale ownership after team changes | Low | Add CODEOWNERS review to periodic maintenance checklist |

### IPFS Test Pattern Note

The investigation report included `tests/test_ipfs_*.py` as a security-critical
test pattern. However, GitHub CODEOWNERS glob support has limitations. Since IPFS
tests primarily test the `ipfs.py` CLI wrapper (which is covered by source-level
ownership), the general `tests/` -> QA rule is sufficient. If specific IPFS test
file ownership is needed later, add explicit file paths (e.g., `tests/test_ipfs_publish.py`).

---

## Testing Strategy

This change adds a configuration file only (no code changes), so testing focuses on
validation rather than functional testing:

1. **Pre-commit**: `ruff check` and `pytest` pass (no regression)
2. **Syntax validation**: GitHub parses CODEOWNERS on push; errors appear in Settings
3. **Functional validation**: Test PR with changes to security-critical, DevOps, and
   default paths to confirm automatic reviewer assignment
4. **Acceptance criteria verification**: All 3 criteria from ticket specification

---

## Commit Message

```
docs: add CODEOWNERS for automatic review assignment (T-016)

Add .github/CODEOWNERS to enable GitHub automatic review requests:

- Default: @helix-oss/maintainers for all files
- Security-critical: @helix-oss/security-reviewers for container.py,
  codec.py, ipfs.py, storage.py, pinning.py, errors.py
- CI/DevOps: @helix-oss/devops for .github/, scripts/, pyproject.toml
- Tests: @helix-oss/qa for tests/ with security test overrides
- Specs: dual ownership for FORMAT.md (maintainers + security)

Team names are placeholders; replace with actual GitHub teams/usernames
before enabling CODEOWNERS enforcement.
```

---

## Notes and Caveats

### Placeholder Team Names

The CODEOWNERS file uses `@helix-oss/<team>` placeholders. Before the file
becomes functional:

1. Create the teams in the GitHub organization, OR
2. Replace team references with individual `@username` references

If teams do not exist, GitHub will:
- Show warnings in Settings > Code review > CODEOWNERS errors
- NOT block PRs (review requests simply will not be sent)
- NOT cause CI failures

### When to Update CODEOWNERS

- New module added to `src/helix/` -- add ownership rule if security-critical
- Team membership changes -- update GitHub team (no file change needed)
- New workflow added to `.github/workflows/` -- covered by `.github/` pattern
- Repository structure changes (e.g., new top-level directories)

### Relationship to Branch Protection (T-018)

T-018 (Repository Settings Hardening) can optionally enable "Require review from
Code Owners" in branch protection rules. This makes CODEOWNERS enforcement mandatory
rather than advisory. T-016 should be completed first so rules are in place when
T-018 enables enforcement.

---

## Claude Code Workflow

**Category**: Community | **Size**: S

**Selected Pattern**: `Community / S` from workflow-patterns.md:
`Direct implementation -> /review (optional) -> /commit`

| Phase | Command / Agent | Purpose |
|-------|----------------|---------|
| 1. Implementation | Direct implementation | Create `.github/CODEOWNERS` (single file, ~55 lines) |
| 2. Review | `/review` | Validate ownership rules and pattern correctness |
| 3. Commit | `/commit` | Conventional commit with `docs:` prefix |

### Execution Example

```
(create .github/CODEOWNERS) -> /review -> /commit
```

### Post-Merge Manual Steps

1. Verify CODEOWNERS in GitHub Settings (no validation errors)
2. Create test PR to confirm automatic reviewer assignment
3. (Optional) Enable "Require review from Code Owners" in branch protection

---

**Document Status**: Ready for Implementation
**Created**: 2026-03-06
**Investigation Reference**: `docs/research/T-016_codeowners_investigation.md`
