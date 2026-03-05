---
paths:
  - "src/helix/container.py"
  - "src/helix/codec.py"
  - "src/helix/ipfs.py"
  - "src/helix/pinning.py"
---
# Security Rules

- Container parsing MUST validate magic bytes, section lengths, and CRC before processing → prevent malformed input attacks
- Verify logic MUST NOT silently pass on integrity mismatch → raise with HELIX_E_* error code and actionable hint
- IPFS subprocess calls MUST sanitize arguments → no shell injection via user-supplied CIDs or paths
- `helix publish` MUST warn on unencrypted seed publication → reduce accidental public data leakage
- Encryption uses HLE1 wrapper; MUST NOT mix HLE1/HLX1 semantics without explicit version handling
- When modifying these paths → read `docs/THREAT_MODEL.md` before implementation
