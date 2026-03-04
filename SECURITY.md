# Security Policy

## Supported Versions
Security fixes are currently provided for:

| Version | Supported |
|---|---|
| 1.0.0a1 | Yes |
| <1.0.0a1 | No |

## Reporting a Vulnerability
If you find a security issue, do not open a public issue first.

Preferred path:
1. Use GitHub Security Advisories (private vulnerability report) for this repository.
2. Include reproduction steps, affected commands/files, and impact.
3. If possible, include a minimal proof-of-concept seed/genome pair.

## Response Expectations
- Initial triage target: within 5 business days.
- Status update cadence: at least weekly until resolution.
- Public disclosure: after patch is available, coordinated with reporter.

## Scope Notes
- Third-party tools (`ipfs`, OS package managers, Python runtime) are out of direct code scope.
- Helix-specific issues (seed parsing, integrity verification, encryption/signature handling, CLI behavior) are in scope.
