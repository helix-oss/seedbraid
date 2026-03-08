# Seedbraid OCI/ORAS Distribution (SBD-ECO-004)

This example provides scripts for pushing and pulling Seedbraid `*.sbd` seeds via
OCI registries with ORAS.

## Media Type and Annotation Convention

Seedbraid uses the following OCI metadata convention:

- Artifact type: `application/vnd.seedbraid.seed.v1`
- Layer media type: `application/vnd.seedbraid.seed.layer.v1+sbd`
- Annotations:
  - `io.seedbraid.seed.source-sha256`
  - `io.seedbraid.seed.chunker`
  - `io.seedbraid.seed.manifest-private`
  - `org.opencontainers.image.title`

## Prerequisites

- `uv` on `PATH`
- `oras` on `PATH`
- Registry login completed (`oras login ...`)

Check ORAS installation:

```bash
oras version
```

## Push and Pull

```bash
# from repository root
examples/oci/scripts/push_seed.sh ./seed.sbd ghcr.io/<owner>/<repo>/seedbraid-seed:latest
examples/oci/scripts/pull_seed.sh ghcr.io/<owner>/<repo>/seedbraid-seed:latest ./pulled.sbd
```

Verify pulled seed integrity:

```bash
uv run --no-sync --no-editable seedbraid verify ./pulled.sbd --genome ./genome --strict
```

## Registry Usage Notes

### GHCR

```bash
echo "$GITHUB_TOKEN" | oras login ghcr.io -u <github-user> --password-stdin
```

Reference format:
`ghcr.io/<owner>/<repo>/seedbraid-seed:<tag>`

### Amazon ECR

```bash
aws ecr get-login-password --region <region> \
  | oras login <account>.dkr.ecr.<region>.amazonaws.com -u AWS --password-stdin
```

Reference format:
`<account>.dkr.ecr.<region>.amazonaws.com/<repository>:<tag>`

### Google Artifact Registry (GAR)

```bash
gcloud auth print-access-token \
  | oras login <region>-docker.pkg.dev -u oauth2accesstoken --password-stdin
```

Reference format:
`<region>-docker.pkg.dev/<project>/<repository>/seedbraid-seed:<tag>`

## Troubleshooting

- Auth failures (`401`/`403`): rerun `oras login`, then verify push/pull permission.
- Reference errors (`name unknown`, `manifest unknown`): confirm repository path/tag.
- Media type mismatch: repush with Seedbraid defaults or pass explicit
  `--artifact-type application/vnd.seedbraid.seed.v1`
  `--media-type application/vnd.seedbraid.seed.layer.v1+sbd`.
- Encrypted seed push fails metadata extraction: provide `--encryption-key` or set
  `SB_ENCRYPTION_KEY` before running push script.

## Out of Scope

- This example does not automate IAM role/policy provisioning for GHCR/ECR/GAR.
