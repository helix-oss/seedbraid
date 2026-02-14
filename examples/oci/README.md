# Helix OCI/ORAS Distribution (HLX-ECO-004)

This example provides scripts for pushing and pulling Helix `*.hlx` seeds via
OCI registries with ORAS.

## Media Type and Annotation Convention

Helix uses the following OCI metadata convention:

- Artifact type: `application/vnd.helix.seed.v1`
- Layer media type: `application/vnd.helix.seed.layer.v1+hlx`
- Annotations:
  - `io.helix.seed.source-sha256`
  - `io.helix.seed.chunker`
  - `io.helix.seed.manifest-private`
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
examples/oci/scripts/push_seed.sh ./seed.hlx ghcr.io/<owner>/<repo>/helix-seed:latest
examples/oci/scripts/pull_seed.sh ghcr.io/<owner>/<repo>/helix-seed:latest ./pulled.hlx
```

Verify pulled seed integrity:

```bash
uv run --no-sync --no-editable helix verify ./pulled.hlx --genome ./genome --strict
```

## Registry Usage Notes

### GHCR

```bash
echo "$GITHUB_TOKEN" | oras login ghcr.io -u <github-user> --password-stdin
```

Reference format:
`ghcr.io/<owner>/<repo>/helix-seed:<tag>`

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
`<region>-docker.pkg.dev/<project>/<repository>/helix-seed:<tag>`

## Troubleshooting

- Auth failures (`401`/`403`): rerun `oras login`, then verify push/pull permission.
- Reference errors (`name unknown`, `manifest unknown`): confirm repository path/tag.
- Media type mismatch: repush with Helix defaults or pass explicit
  `--artifact-type application/vnd.helix.seed.v1`
  `--media-type application/vnd.helix.seed.layer.v1+hlx`.
- Encrypted seed push fails metadata extraction: provide `--encryption-key` or set
  `HELIX_ENCRYPTION_KEY` before running push script.

## Out of Scope

- This example does not automate IAM role/policy provisioning for GHCR/ECR/GAR.
