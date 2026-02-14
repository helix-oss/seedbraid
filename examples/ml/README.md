# Helix ML Tooling Hooks (HLX-ECO-005)

This example provides optional scripts for:

- logging Helix seed metadata to MLflow
- uploading seed + metadata sidecar to Hugging Face Hub

## Prerequisites

- `uv` on `PATH`
- For MLflow logging: reachable `MLFLOW_TRACKING_URI`
- For Hugging Face upload: `huggingface-cli` (or `hf`) on `PATH`

## 1) Log Metadata to MLflow

Set credentials and endpoint in environment variables:

```bash
export MLFLOW_TRACKING_URI="https://mlflow.example"
export MLFLOW_TRACKING_TOKEN="<token>" # optional if server is open or uses other auth
```

Run:

```bash
# from repository root
examples/ml/scripts/log_mlflow.sh ./seed.hlx \
  --experiment helix-seeds \
  --run-name seed-2026-02-14 \
  --cid bafy... \
  --oci-reference ghcr.io/acme/helix-seed:v1
```

This writes metadata sidecar `seed.hlx.metadata.json` and logs the same fields to MLflow params.

## 2) Upload Seed + Metadata to Hugging Face Hub

Set token in environment variable:

```bash
export HF_TOKEN="<token>"
```

Run:

```bash
# from repository root
examples/ml/scripts/upload_hf.sh ./seed.hlx <org-or-user>/<repo> \
  --repo-type dataset \
  --revision main \
  --remote-prefix helix/seeds
```

The script uploads both:

- `seed.hlx`
- `seed.hlx.metadata.json` (auto-generated if missing)

## Restore from Logged Metadata

Given metadata with seed pointer (`ipfs_cid` or `oci_reference`):

1. Retrieve seed bytes to local file (`seed.hlx`) from the referenced transport.
2. Ensure required genome data is available locally (or use portable seed).
3. Verify integrity strictly:

```bash
uv run --no-sync --no-editable helix verify ./seed.hlx --genome ./genome --strict
```

4. Decode when needed:

```bash
uv run --no-sync --no-editable helix decode ./seed.hlx --genome ./genome --out ./recovered.bin
```

For encrypted HLE1 seeds, pass `--encryption-key` or set `HELIX_ENCRYPTION_KEY`.

## Security Caveats

- Metadata may reveal provenance fields (`source_sha256`, chunker, CID/OCI reference).
- For public registries/hubs, prefer `helix encode --manifest-private --encrypt`.
- Treat API tokens (`MLFLOW_TRACKING_TOKEN`, `HF_TOKEN`) as secrets; do not commit them.
