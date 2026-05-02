# Security checklist (OWASP ASVS L1 alignment)

A practical, line-item view of how CivicGuide stacks up against the OWASP
Application Security Verification Standard (ASVS) Level 1 — the minimum
bar for a public-facing application. Each item links to where the
control lives in the codebase.

| ASVS § | Requirement | Status | Where |
|---|---|---|---|
| **V1: Architecture** | | | |
| 1.1.4 | All components are defined as services with clear boundaries | ✅ | `app/services/*` |
| 1.5.1 | Untrusted data is treated consistently across layers | ✅ | `app/safety.py`, `app/schemas.py` |
| **V2: Authentication** | (no per-user auth in this build — public read-only) | n/a | — |
| **V3: Session management** | (stateless API; client-supplied session_id) | n/a | — |
| **V4: Access control** | | | |
| 4.1.1 | Trusted enforcement point (server-side) for all access decisions | ✅ | FastAPI dependencies |
| 4.2.1 | Sensitive data not exposed in URLs | ✅ | All POST endpoints; no query strings |
| **V5: Validation, sanitisation, encoding** | | | |
| 5.1.1 | Inputs are validated against a positive (allow-list) schema | ✅ | `app/schemas.py` Pydantic v2 |
| 5.1.3 | Length / range limits on every input | ✅ | `Field(min_length=, max_length=, ge=, le=)` |
| 5.1.4 | Allowed character set enforced for free-text fields | ✅ | Sanitisation in `app/safety.py` |
| 5.2.3 | Server outputs are properly encoded for the destination | ✅ | JSON responses via Pydantic; HTML via `escapeHtml` in `static/app.js` |
| 5.2.4 | Untrusted markup is escaped before DOM injection | ✅ | `escapeHtml` then minimal Markdown |
| 5.3.3 | All user-supplied output is encoded for HTML context | ✅ | `escapeHtml` |
| **V7: Errors and logging** | | | |
| 7.1.1 | Logs include enough detail to investigate (request id, user-agent) | ✅ | Request-ID middleware in `app/main.py` |
| 7.2.1 | Sensitive data not logged | ✅ | PII redacted before logging via `app/safety.py` |
| **V8: Data protection** | | | |
| 8.1.1 | Inputs are not stored beyond the lifetime of the request | ✅ | Stateless service |
| 8.3.4 | Sensitive data only sent over HTTPS | ✅ | HSTS preload + redirect-to-HTTPS at Cloud Run |
| **V9: Communication** | | | |
| 9.1.1 | TLS 1.2+ used for all external connections | ✅ | Cloud Run TLS termination + httpx defaults |
| **V10: Malicious code** | | | |
| 10.3.2 | Build artifacts come from trusted sources | ✅ | Pinned `requirements.txt`, dependabot, `pip-audit` |
| **V11: Business logic** | | | |
| 11.1.1 | Business logic flows are documented | ✅ | `ARCHITECTURE.md` flow diagrams |
| **V12: Files and resources** | | | |
| 12.4.1 | User uploads not accepted (none in this build) | ✅ | n/a (no upload endpoint) |
| **V13: API and web service** | | | |
| 13.1.1 | All APIs are authenticated where appropriate | n/a | (public read-only) |
| 13.1.4 | All APIs have rate-limiting or other anti-abuse | ✅ | slowapi 30 req/min/IP |
| 13.2.1 | Schemas validated against an OpenAPI spec | ✅ | Auto-generated `/openapi.json` |
| **V14: Configuration** | | | |
| 14.1.1 | App configuration is independent of deployment | ✅ | `app/config.py` (12-factor) |
| 14.1.5 | Production config has no debug / verbose modes enabled | ✅ | `LOG_LEVEL=info`, no `--reload` |
| 14.2.1 | Components don't have known vulnerable versions | ✅ | dependabot + pip-audit in CI |
| 14.2.2 | Unused dependencies are removed | ✅ | Reviewed manually each commit |
| 14.3.2 | Unintended source code (debug, comments) not exposed | ✅ | `.dockerignore` excludes `.git`, tests, etc. |
| 14.4.1 | All HTTP responses include a Content-Type header | ✅ | FastAPI default + explicit on file responses |
| 14.4.2 | All HTTP headers / responses contain `X-Content-Type-Options: nosniff` | ✅ | security middleware |
| 14.4.3 | A strict CSP is enforced for HTML responses | ✅ | security middleware |
| 14.4.5 | HSTS is enabled with preload | ✅ | security middleware (HTTPS only) |
| 14.4.6 | Frame-options/CSP frame-ancestors prevent clickjacking | ✅ | `X-Frame-Options: DENY` + `frame-ancestors 'none'` |
| 14.4.7 | Cross-domain resource sharing is restrictive | ✅ | CORS allow-list, not `*` |

## Continuous verification

| Tool | Purpose | When it runs |
|---|---|---|
| `bandit` | Python static analysis for common security smells | Every PR (CI) + pre-commit |
| `pip-audit` | Dependency CVE scan | Every PR (CI) + weekly schedule |
| `dependabot` | Auto-PR for vulnerable / outdated deps | Weekly |
| `CodeQL` | Deep semantic SAST (Python + JavaScript) | Every PR (CI) + weekly schedule |
| GitHub Secret Scanning + Push Protection | Block accidental secret commits | Every push (server-side) |

## Responsible disclosure

See [`SECURITY.md`](../SECURITY.md). The maintainer commits to:

- **72 hours** to acknowledge a report
- **7 days** to a status update
- **30 days** target for a coordinated fix + disclosure
