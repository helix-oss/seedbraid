---
paths:
  - "src/seedbraid/container.py"
  - "src/seedbraid/codec.py"
  - "src/seedbraid/ipfs.py"
  - "src/seedbraid/pinning.py"
---
# Security Rules

- Container parsing MUST validate magic bytes, section lengths, and CRC before processing → prevent malformed input attacks
- Verify logic MUST NOT silently pass on integrity mismatch → raise with SB_E_* error code and actionable hint
- IPFS subprocess calls MUST sanitize arguments → no shell injection via user-supplied CIDs or paths
- `seedbraid publish` MUST warn on unencrypted seed publication → reduce accidental public data leakage
- Encryption uses SBE1 wrapper; MUST NOT mix SBE1/SBD1 semantics without explicit version handling
- When modifying these paths → read `docs/THREAT_MODEL.md` before implementation
