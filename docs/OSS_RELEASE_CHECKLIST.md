# OSS Release Checklist

Use this checklist before making the repository public.

## 1. Personal Information Audit (Required)
- Check commit identity:
```bash
git log --pretty=format:'%h %an <%ae>' -n 200
```
- Check for machine/user/path leakage in tracked files:
```bash
rg -n --hidden -S "(/Users/|\\.local|@|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|AKIA|token|secret|password)" . --glob '!.git/*'
```
- If personal identity appears in history, rewrite history before public push.

## 2. Secret and Artifact Audit (Required)
- Verify no secrets or local runtime files are tracked:
```bash
git ls-files '*.env' '*.pem' '*.key' '*.p12' '*.sqlite' '*.db'
```
- Ensure `.gitignore` covers local outputs (`.artifacts/`, runtime genomes, caches).

## 3. License and Policy Files (Required)
- `LICENSE` exists and matches intended terms.
- `SECURITY.md` exists with private reporting instructions.
- `CONTRIBUTING.md` exists with setup and quality gate commands.

## 4. Quality Gates (Required)
```bash
UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check .
PYTHONPATH=src UV_CACHE_DIR=.uv-cache uv run --no-editable python -m pytest
```

## 5. Format and Compatibility (Required)
- Compatibility fixtures are present and tests are green:
```bash
uv run --no-editable python -m pytest tests/test_compat_fixtures.py
```
- If HLX behavior changed intentionally:
  - update `docs/FORMAT.md`
  - update `docs/DESIGN.md`
  - regenerate fixtures intentionally and document why

## 6. Release Metadata (Recommended)
- Add release notes summarizing user-facing changes.
- Tag release version and include migration notes if needed.
