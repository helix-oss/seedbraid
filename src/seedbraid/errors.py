"""Seedbraid exception hierarchy and reusable next-action constants.

All domain errors derive from ``SeedbraidError`` and carry structured
error codes plus actionable recovery hints.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorCodeInfo:
    code: str
    message: str
    next_action: str | None = None


class SeedbraidError(Exception):
    """Base error for Seedbraid operations."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "SB_E_UNKNOWN",
        next_action: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.next_action = next_action

    def as_info(self) -> ErrorCodeInfo:
        return ErrorCodeInfo(
            code=self.code,
            message=str(self),
            next_action=self.next_action,
        )


class SeedFormatError(SeedbraidError):
    """Raised when SBD1 seed structure or integrity checks fail."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "SB_E_SEED_FORMAT",
        next_action: str | None = None,
    ) -> None:
        super().__init__(message, code=code, next_action=next_action)


class DecodeError(SeedbraidError):
    """Raised when reconstruction cannot proceed."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "SB_E_DECODE",
        next_action: str | None = None,
    ) -> None:
        super().__init__(message, code=code, next_action=next_action)


class ExternalToolError(SeedbraidError):
    """Raised when external tools (e.g., ipfs) are unavailable or fail."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "SB_E_EXTERNAL_TOOL",
        next_action: str | None = None,
    ) -> None:
        super().__init__(message, code=code, next_action=next_action)


# -- next_action templates -----------------------------------------
ACTION_VERIFY_SEED = (
    "Verify seed file integrity or regenerate"
    " with `seedbraid encode`."
)
ACTION_REGENERATE_SEED = (
    "Regenerate the seed file with `seedbraid encode`."
)
ACTION_REFETCH_SEED = (
    "Re-download or re-transfer the seed file."
)
ACTION_UPGRADE_SEEDBRAID = (
    "Upgrade Seedbraid to the latest version."
)
ACTION_VERIFY_ENCRYPTION = (
    "Verify encryption key/password is correct."
)
ACTION_PROVIDE_ENCRYPTION_KEY = (
    "Provide --encryption-key"
    " or set SB_ENCRYPTION_KEY."
)
ACTION_INSTALL_ZSTD = (
    "Run `uv sync --extra zstd`"
    " to install zstandard."
)
ACTION_CHECK_OPTIONS = (
    "Check command-line options and retry."
)
ACTION_REPORT_BUG = (
    "This is likely a bug. Please report it."
)
ACTION_CHECK_GENOME = (
    "Check genome database,"
    " or run `seedbraid prime` to rebuild."
)
ACTION_VERIFY_SNAPSHOT = (
    "Verify the snapshot file or regenerate"
    " with `seedbraid genome snapshot`."
)
ACTION_VERIFY_GENES_PACK = (
    "Verify the genes pack file or regenerate"
    " with `seedbraid export-genes`."
)
ACTION_CHECK_DISK = (
    "Check directory permissions"
    " and available disk space."
)
ACTION_ENABLE_LEARN_OR_PORTABLE = (
    "Enable --learn or --portable"
    " for unknown chunks."
)
ACTION_INSTALL_CRYPTO = (
    "Run `uv sync --extra crypto`"
    " to install cryptography."
)
ACTION_REGENERATE_MANIFEST = (
    "Regenerate manifest with"
    " `seedbraid publish-chunks`."
)
ACTION_CHECK_IPFS_DAEMON = (
    "Ensure kubo daemon is running"
    " (`ipfs daemon`) and the API"
    " endpoint is accessible."
    " Check with `seedbraid doctor`."
)
ACTION_CHECK_KUBO_API = (
    "Ensure kubo daemon is running"
    " (`ipfs daemon`) and SB_KUBO_API"
    " points to the correct endpoint."
    " Default: http://127.0.0.1:5001/api/v0."
)
ACTION_CHECK_IPFS_NETWORK = (
    "Check IPFS network connectivity"
    " or provide --gateway for fallback."
)
ACTION_CHECK_IPFS_MFS = (
    "Verify IPFS daemon is running and"
    " MFS is accessible with"
    " `ipfs files ls /`."
)
