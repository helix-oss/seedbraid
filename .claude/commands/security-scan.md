---
description: "Run security audit on security-sensitive modules"
argument-hint: "[target module or file (optional, defaults to all)]"
---

Run security audit. Target: $ARGUMENTS

Security-sensitive modules:
- `src/seedbraid/container.py` — SBD1 binary format parsing
- `src/seedbraid/codec.py` — encoding/decoding
- `src/seedbraid/ipfs.py` — IPFS transport
- `src/seedbraid/ipfs_http.py` — kubo HTTP RPC client
- `src/seedbraid/ipfs_chunks.py` — IPFS distributed chunk operations
- `src/seedbraid/cid.py` — CID validation and computation
- `src/seedbraid/chunk_manifest.py` — chunk manifest integrity
- `src/seedbraid/pinning.py` — IPFS pinning services

## Instructions

1. Spawn the **security-scanner** agent on the target
   - If no target specified, audit all security-sensitive modules
2. The scanner will reference `docs/THREAT_MODEL.md` for known threats
3. Full report will be saved to `.docs/reviews/security-{topic}.md`
4. Report findings by severity: Critical > High > Medium > Low
5. If critical issues found, recommend immediate remediation
