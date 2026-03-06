from __future__ import annotations

import os
import re
import secrets
from pathlib import Path

import typer

from .chunking import ChunkerConfig
from .codec import (
    decode_file,
    encode_file,
    export_genes,
    import_genes,
    prime_genome,
    restore_genome,
    snapshot_genome,
    verify_seed,
)
from .container import is_encrypted_seed_data, sign_seed_file
from .diagnostics import run_doctor
from .errors import ExternalToolError, HelixError
from .ipfs import fetch_seed, pin_health_status, publish_seed, remote_pin_cid

app = typer.Typer(help="Helix CLI")
genome_app = typer.Typer(help="Genome backup and restore operations")
pin_app = typer.Typer(help="IPFS pin operations")
app.add_typer(genome_app, name="genome")
app.add_typer(pin_app, name="pin")
ENV_VAR_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _cfg(
    avg: int,
    min_size: int,
    max_size: int,
    window_size: int = 64,
) -> ChunkerConfig:
    if min_size <= 0 or avg <= 0 or max_size <= 0:
        raise typer.BadParameter("Chunk sizes must be > 0")
    if not (min_size <= avg <= max_size):
        raise typer.BadParameter("Require min <= avg <= max")
    return ChunkerConfig(
        min_size=min_size,
        avg_size=avg,
        max_size=max_size,
        window_size=window_size,
    )


@app.command()
def encode(
    file: Path,
    genome: Path = typer.Option(..., "--genome"),
    out: Path = typer.Option(..., "--out"),
    chunker: str = typer.Option("cdc_buzhash", "--chunker"),
    avg: int = typer.Option(65_536, "--avg"),
    min_size: int = typer.Option(16_384, "--min"),
    max_size: int = typer.Option(262_144, "--max"),
    learn: bool = typer.Option(True, "--learn/--no-learn"),
    portable: bool = typer.Option(False, "--portable/--no-portable"),
    compression: str = typer.Option("zlib", "--compression"),
    manifest_private: bool = typer.Option(
        False,
        "--manifest-private/--no-manifest-private",
        help="Minimize manifest metadata for lower information leakage.",
    ),
    encrypt: bool = typer.Option(False, "--encrypt/--no-encrypt"),
    encryption_key: str | None = typer.Option(
        None,
        "--encryption-key",
        help="Passphrase for HLE1 encrypted seed output.",
    ),
) -> None:
    """Encode a file into HLX1 seed."""
    if encrypt and not encryption_key:
        raise typer.Exit(
            code=_print_error(
                HelixError(
                    "Encryption key is required when --encrypt is enabled. "
                    "Use --encryption-key or HELIX_ENCRYPTION_KEY.",
                    code="HELIX_E_ENCRYPTION_KEY_MISSING",
                    next_action=(
                        "Pass `--encryption-key <secret>`"
                        " or set HELIX_ENCRYPTION_KEY."
                    ),
                )
            )
        )
    effective_encryption_key = (
        encryption_key
        or os.environ.get("HELIX_ENCRYPTION_KEY")
    )
    if encrypt and not effective_encryption_key:
        raise typer.Exit(
            code=_print_error(
                HelixError(
                    "HELIX_ENCRYPTION_KEY is not set. "
                    "Provide --encryption-key or set HELIX_ENCRYPTION_KEY.",
                    code="HELIX_E_ENCRYPTION_KEY_MISSING",
                    next_action=(
                        "Export HELIX_ENCRYPTION_KEY"
                        " or pass `--encryption-key`"
                        " directly."
                    ),
                )
            )
        )
    try:
        stats = encode_file(
            in_path=file,
            genome_path=genome,
            out_seed_path=out,
            chunker=chunker,
            cfg=_cfg(avg, min_size, max_size),
            learn=learn,
            portable=portable,
            manifest_compression=compression,
            manifest_private=manifest_private,
            encryption_key=effective_encryption_key if encrypt else None,
        )
        typer.echo(
            "encoded "
            f"chunks={stats.total_chunks} reused={stats.reused_chunks} "
            f"new={stats.new_chunks} "
            f"raw={stats.raw_chunks} "
            f"unique={stats.unique_hashes}"
        )
    except HelixError as exc:
        raise typer.Exit(code=_print_error(exc))


@app.command()
def decode(
    seed: Path,
    genome: Path = typer.Option(..., "--genome"),
    out: Path = typer.Option(..., "--out"),
    encryption_key: str | None = typer.Option(
        None,
        "--encryption-key",
        help="Passphrase for encrypted HLE1 seed input.",
    ),
) -> None:
    """Decode a seed into original file."""
    try:
        digest = decode_file(
            seed,
            genome,
            out,
            encryption_key=(
                encryption_key
                or os.environ.get("HELIX_ENCRYPTION_KEY")
            ),
        )
        typer.echo(f"decoded sha256={digest}")
    except HelixError as exc:
        raise typer.Exit(code=_print_error(exc))


@app.command()
def verify(
    seed: Path,
    genome: Path = typer.Option(..., "--genome"),
    strict: bool = typer.Option(
        False,
        "--strict/--no-strict",
        help="Reconstruct all chunks and enforce source size/SHA-256 match.",
    ),
    require_signature: bool = typer.Option(
        False,
        "--require-signature/--no-require-signature",
        help="Fail verify when signature is missing or invalid.",
    ),
    signature_key: str | None = typer.Option(
        None,
        "--signature-key",
        help="HMAC key used to validate seed signature.",
    ),
    encryption_key: str | None = typer.Option(
        None,
        "--encryption-key",
        help="Passphrase for encrypted HLE1 seed input.",
    ),
) -> None:
    """Verify seed integrity and reconstructability."""
    try:
        report = verify_seed(
            seed,
            genome,
            strict=strict,
            require_signature=require_signature,
            signature_key=signature_key,
            encryption_key=(
                encryption_key
                or os.environ.get("HELIX_ENCRYPTION_KEY")
            ),
        )
    except HelixError as exc:
        raise typer.Exit(code=_print_error(exc))

    if report.ok:
        typer.echo(
            f"verify ok mode={'strict' if strict else 'quick'} "
            f"expected_sha256={report.expected_sha256} "
            f"actual_sha256={report.actual_sha256}"
        )
        raise typer.Exit(code=0)

    typer.echo(f"verify failed: {report.reason}", err=True)
    if report.missing_count:
        typer.echo(f"missing_count={report.missing_count}", err=True)
        for h in report.missing_hashes:
            typer.echo(f"missing_chunk={h}", err=True)
    if report.expected_sha256 or report.actual_sha256:
        typer.echo(
            f"expected_sha256={report.expected_sha256} "
            f"actual_sha256={report.actual_sha256}",
            err=True,
        )
    raise typer.Exit(code=1)


@app.command()
def prime(
    dir_or_glob: str,
    genome: Path = typer.Option(..., "--genome"),
    chunker: str = typer.Option("cdc_buzhash", "--chunker"),
    avg: int = typer.Option(65_536, "--avg"),
    min_size: int = typer.Option(16_384, "--min"),
    max_size: int = typer.Option(262_144, "--max"),
) -> None:
    """Prime genome with chunks from a directory or glob."""
    try:
        stats = prime_genome(
            dir_or_glob=dir_or_glob,
            genome_path=genome,
            chunker=chunker,
            cfg=_cfg(avg, min_size, max_size),
        )
        typer.echo(
            "prime "
            f"files={stats['files']} total_chunks={stats['total_chunks']} "
            f"new_chunks={stats['new_chunks']} "
            f"reused_chunks={stats['reused_chunks']} "
            f"dedup_ratio="
            f"{stats['dedup_ratio_bps']/100:.2f}%"
        )
    except HelixError as exc:
        raise typer.Exit(code=_print_error(exc))


@app.command()
def publish(
    seed: Path,
    pin: bool = typer.Option(False, "--pin/--no-pin"),
    remote_pin: bool = typer.Option(
        False,
        "--remote-pin/--no-remote-pin",
        help="Register published CID with remote pinning provider.",
    ),
    remote_provider: str = typer.Option(
        "psa",
        "--remote-provider",
        help="Remote pin provider key (currently: psa).",
    ),
    remote_endpoint: str | None = typer.Option(
        None,
        "--remote-endpoint",
        help="Remote pin API endpoint. Defaults to HELIX_PINNING_ENDPOINT.",
    ),
    remote_token: str | None = typer.Option(
        None,
        "--remote-token",
        help="Remote pin API bearer token. Defaults to HELIX_PINNING_TOKEN.",
    ),
    remote_name: str | None = typer.Option(
        None,
        "--remote-name",
        help=(
            "Optional remote pin name."
            " Defaults to seed filename when omitted."
        ),
    ),
    remote_timeout_ms: int = typer.Option(
        10_000,
        "--remote-timeout-ms",
        min=1,
        help="Remote pin request timeout in milliseconds.",
    ),
    remote_retries: int = typer.Option(
        3,
        "--remote-retries",
        min=1,
        help="Remote pin retry attempts.",
    ),
    remote_backoff_ms: int = typer.Option(
        200,
        "--remote-backoff-ms",
        min=0,
        help="Remote pin exponential backoff base in milliseconds.",
    ),
) -> None:
    """Publish seed to IPFS and output CID."""
    try:
        with seed.open("rb") as f:
            if not is_encrypted_seed_data(f.read(4)):
                typer.echo(
                    "warning: publishing unencrypted seed. "
                    "Consider `helix encode --encrypt"
                    " --manifest-private`"
                    " for sensitive data.",
                    err=True,
                )
    except OSError:
        # publish_seed will emit actionable error
        # if the file is missing/unreadable.
        pass
    try:
        cid = publish_seed(seed, pin=pin)
    except (HelixError, ExternalToolError) as exc:
        raise typer.Exit(code=_print_error(exc))

    if remote_pin:
        try:
            report = remote_pin_cid(
                cid,
                provider=remote_provider,
                endpoint=remote_endpoint,
                token=remote_token,
                name=remote_name or seed.name,
                timeout_ms=remote_timeout_ms,
                retries=remote_retries,
                backoff_ms=remote_backoff_ms,
            )
        except (HelixError, ExternalToolError) as exc:
            raise typer.Exit(code=_print_error(exc))
        typer.echo(
            "remote_pin "
            f"provider={report.provider} "
            f"cid={report.cid} "
            f"status={report.status} "
            f"request_id="
            f"{report.request_id or 'none'}"
        )

    typer.echo(cid)


@app.command()
def fetch(
    cid: str,
    out: Path = typer.Option(..., "--out"),
    retries: int = typer.Option(
        3,
        "--retries",
        min=1,
        help="Number of ipfs cat attempts before failing or gateway fallback.",
    ),
    backoff_ms: int = typer.Option(
        200,
        "--backoff-ms",
        min=0,
        help="Base backoff in milliseconds (exponential).",
    ),
    gateway: str | None = typer.Option(
        None,
        "--gateway",
        help="Optional HTTP gateway base URL, e.g. https://ipfs.io/ipfs",
    ),
) -> None:
    """Fetch seed from IPFS CID."""
    try:
        fetch_seed(
            cid, out,
            retries=retries,
            backoff_ms=backoff_ms,
            gateway=gateway,
        )
    except (HelixError, ExternalToolError) as exc:
        raise typer.Exit(code=_print_error(exc))
    typer.echo(f"fetched {cid} -> {out}")


@app.command("pin-health")
def pin_health(cid: str) -> None:
    """Check local pin status and block availability for CID."""
    try:
        report = pin_health_status(cid)
    except (HelixError, ExternalToolError) as exc:
        raise typer.Exit(code=_print_error(exc))

    typer.echo(
        f"pin_health cid={report['cid']} "
        f"pinned={report['pinned']} "
        f"pin_type={report['pin_type']} "
        f"block_available="
        f"{report['block_available']}"
    )
    if report["reason"]:
        typer.echo(
            f"reason={report['reason']}",
            err=not bool(report["ok"]),
        )
    raise typer.Exit(code=0 if report["ok"] else 1)


@pin_app.command("remote-add")
def pin_remote_add(
    cid: str,
    provider: str = typer.Option(
        "psa",
        "--provider",
        help="Remote pin provider key (currently: psa).",
    ),
    endpoint: str | None = typer.Option(
        None,
        "--endpoint",
        help="Remote pin API endpoint. Defaults to HELIX_PINNING_ENDPOINT.",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        help="Remote pin API bearer token. Defaults to HELIX_PINNING_TOKEN.",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help="Optional display name for remote pin request.",
    ),
    timeout_ms: int = typer.Option(
        10_000,
        "--timeout-ms",
        min=1,
        help="Remote pin request timeout in milliseconds.",
    ),
    retries: int = typer.Option(
        3,
        "--retries",
        min=1,
        help="Remote pin retry attempts.",
    ),
    backoff_ms: int = typer.Option(
        200,
        "--backoff-ms",
        min=0,
        help="Remote pin exponential backoff base in milliseconds.",
    ),
) -> None:
    """Register existing CID with remote pinning provider."""
    try:
        report = remote_pin_cid(
            cid,
            provider=provider,
            endpoint=endpoint,
            token=token,
            name=name,
            timeout_ms=timeout_ms,
            retries=retries,
            backoff_ms=backoff_ms,
        )
    except (HelixError, ExternalToolError) as exc:
        raise typer.Exit(code=_print_error(exc))

    typer.echo(
        "remote_pin "
        f"provider={report.provider} "
        f"cid={report.cid} "
        f"status={report.status} "
        f"request_id="
        f"{report.request_id or 'none'}"
    )


@app.command()
def doctor(
    genome: Path = typer.Option(Path("./genome"), "--genome"),
) -> None:
    """Run environment and dependency diagnostics."""
    try:
        report = run_doctor(genome)
    except (HelixError, ExternalToolError) as exc:
        raise typer.Exit(code=_print_error(exc))

    for check in report.checks:
        typer.echo(f"[{check.status}] {check.check}: {check.detail}")
        if check.next_action and check.status in {"warn", "fail"}:
            typer.echo(f"next_action: {check.next_action}")

    typer.echo(
        "doctor summary "
        f"ok={report.ok_count} "
        f"warn={report.warn_count} "
        f"fail={report.fail_count}"
    )
    raise typer.Exit(code=0 if report.ok else 1)


@app.command("gen-encryption-key")
def gen_encryption_key(
    bytes_len: int = typer.Option(
        32,
        "--bytes",
        min=16,
        max=64,
        help="Entropy bytes used to generate key material.",
    ),
    shell: bool = typer.Option(
        False,
        "--shell/--no-shell",
        help="Output in shell export format.",
    ),
    env_var: str = typer.Option(
        "HELIX_ENCRYPTION_KEY",
        "--env-var",
        help="Environment variable name used with --shell output.",
    ),
) -> None:
    """Generate a high-entropy passphrase for seed encryption workflows."""
    if shell and ENV_VAR_NAME_RE.fullmatch(env_var) is None:
        raise typer.Exit(
            code=_print_error(
                HelixError(
                    f"Invalid environment variable name: {env_var}",
                    code="HELIX_E_INVALID_OPTION",
                    next_action=(
                        "Use --env-var with"
                        " letters/digits/underscores"
                        " only, starting with a"
                        " letter or underscore."
                    ),
                )
            )
        )

    key = secrets.token_urlsafe(bytes_len)
    if shell:
        typer.echo(f"export {env_var}='{key}'")
    else:
        typer.echo(key)


@app.command()
def sign(
    seed: Path,
    out: Path = typer.Option(..., "--out"),
    key_env: str = typer.Option(
        "HELIX_SIGNING_KEY",
        "--key-env",
        help="Environment variable name that holds signing key.",
    ),
    key_id: str = typer.Option("default", "--key-id"),
) -> None:
    """Sign an existing seed using HMAC-SHA256 signature section."""
    key = os.environ.get(key_env)
    if not key:
        raise typer.Exit(
            code=_print_error(
                HelixError(
                    f"Signing key env var is not set: {key_env}. "
                    "Set it before running `helix sign`.",
                    code="HELIX_E_SIGNING_KEY_MISSING",
                    next_action=(
                        f"Export `{key_env}` with your"
                        " HMAC signing key and retry."
                    ),
                )
            )
        )
    try:
        sign_seed_file(seed, out, signature_key=key, signature_key_id=key_id)
    except HelixError as exc:
        raise typer.Exit(code=_print_error(exc))
    typer.echo(f"signed {seed} -> {out} key_id={key_id}")


@app.command("export-genes")
def export_genes_cmd(
    seed: Path,
    genome: Path = typer.Option(..., "--genome"),
    out: Path = typer.Option(..., "--out"),
) -> None:
    """Export seed-related chunk payloads from genome into genes pack."""
    try:
        stats = export_genes(seed, genome, out)
    except HelixError as exc:
        raise typer.Exit(code=_print_error(exc))
    typer.echo(
        f"exported total={stats['total']} "
        f"exported={stats['exported']} "
        f"missing={stats['missing']}"
    )


@app.command("import-genes")
def import_genes_cmd(
    pack: Path,
    genome: Path = typer.Option(..., "--genome"),
) -> None:
    """Import chunk payloads from genes pack into genome."""
    try:
        stats = import_genes(pack, genome)
    except HelixError as exc:
        raise typer.Exit(code=_print_error(exc))
    typer.echo(
        f"imported inserted={stats['inserted']} "
        f"skipped={stats['skipped']}"
    )


@genome_app.command("snapshot")
def genome_snapshot(
    genome: Path = typer.Option(..., "--genome"),
    out: Path = typer.Option(..., "--out"),
) -> None:
    """Export all genome chunks into a portable snapshot file."""
    try:
        stats = snapshot_genome(genome, out)
    except HelixError as exc:
        raise typer.Exit(code=_print_error(exc))
    typer.echo(
        f"snapshot chunks={stats['chunks']} "
        f"bytes={stats['bytes']} out={out}"
    )


@genome_app.command("restore")
def genome_restore(
    snapshot: Path,
    genome: Path = typer.Option(..., "--genome"),
    replace: bool = typer.Option(
        False,
        "--replace/--no-replace",
        help=(
            "Replace existing genome chunks"
            " before restoring snapshot content."
        ),
    ),
) -> None:
    """Restore genome chunks from snapshot file."""
    try:
        stats = restore_genome(snapshot, genome, replace=replace)
    except HelixError as exc:
        raise typer.Exit(code=_print_error(exc))
    typer.echo(
        f"restored entries={stats['entries']} inserted={stats['inserted']} "
        f"skipped={stats['skipped']}"
    )


def _print_error(exc: Exception) -> int:
    if isinstance(exc, HelixError):
        info = exc.as_info()
        typer.echo(f"error[{info.code}]: {info.message}", err=True)
        if info.next_action:
            typer.echo(f"next_action: {info.next_action}", err=True)
        return 1
    typer.echo(f"error[HELIX_E_UNKNOWN]: {exc}", err=True)
    return 1
