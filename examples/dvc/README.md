# Seedbraid DVC Workflow Bridge (SBD-ECO-003)

This example shows a minimal DVC pipeline that uses Seedbraid seeds in three stages:

1. `encode`: produce `current.sbd` and a genome snapshot.
2. `verify`: run `seedbraid verify --strict` (pipeline fails on integrity mismatch).
3. `fetch`: fetch seed bytes by CID using `seedbraid fetch`.

## Prerequisites

- `uv` available on `PATH`
- `dvc` available on `PATH`
- `ipfs` CLI available on `PATH` and daemon reachable

## IPFS Setup (for fetch stage)

Run this once on a new machine:

```bash
ipfs --version
ipfs init
```

Start daemon in a dedicated terminal:

```bash
ipfs daemon
```

In another terminal, confirm connectivity:

```bash
ipfs id
```

## Run End-to-End Locally

```bash
cd examples/dvc

dvc init --subdir

dvc repro
```

The fetch stage auto-populates `artifacts/metadata/seed.cid` by publishing the
encoded seed when the CID file is absent.

## Stage-by-Stage

```bash
cd examples/dvc

dvc repro encode
dvc repro verify
dvc repro fetch
```

To force a verify failure check, corrupt `artifacts/seed/current.sbd` and rerun
`dvc repro verify`.

## Recommended Artifact Layout

- `artifacts/seed/current.sbd`: canonical Seedbraid seed tracked by DVC.
- `artifacts/genome/snapshot.sgs`: portable genome snapshot for handoff/backup.
- `artifacts/metadata/verify.ok`: strict verification marker.
- `artifacts/metadata/seed.cid`: CID sidecar used by fetch stage.
- `artifacts/fetched/current.sbd`: fetched seed copy for downstream jobs.

## Optional Script Overrides

Scripts use repo-local Seedbraid by default via `uv run --project ../..`.
For custom runners, these environment variables can be set:

- `SB_DVC_SEEDBRAID_BIN`: override Seedbraid executable path.
- `SB_DVC_INPUT_PATH`
- `SB_DVC_GENOME_PATH`
- `SB_DVC_SEED_PATH`
- `SB_DVC_SNAPSHOT_PATH`
- `SB_DVC_VERIFY_OK_PATH`
- `SB_DVC_CID_PATH`
- `SB_DVC_FETCHED_PATH`
