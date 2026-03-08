---
description: "Run security audit on security-sensitive modules"
argument-hint: "[target module or file (optional, defaults to all)]"
---

Run security audit. Target: $ARGUMENTS

Security-sensitive modules:
- `src/helix/container.py` — HLX1 binary format parsing
- `src/helix/codec.py` — encoding/decoding
- `src/helix/ipfs.py` — IPFS transport
- `src/helix/pinning.py` — IPFS pinning services

## Instructions

1. Spawn the **security-scanner** agent on the target
   - If no target specified, audit all security-sensitive modules
2. The scanner will reference `docs/THREAT_MODEL.md` for known threats
3. Full report will be saved to `.docs/reviews/security-{topic}.md`
4. Report findings by severity: Critical > High > Medium > Low
5. If critical issues found, recommend immediate remediation
