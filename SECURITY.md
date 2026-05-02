# Security Policy

## Reporting a vulnerability

If you discover a security issue in CivicGuide, please **do not open a
public GitHub issue**. Instead, email the maintainer privately with:

1. A description of the issue
2. Steps to reproduce
3. The affected version / commit hash
4. Any proof-of-concept payload (in a private repo / encrypted attachment)

You will receive an acknowledgement within 72 hours and a status update
within 7 days.

## Threat model

CivicGuide is designed to be safely exposed on a public, unauthenticated
URL. The threat model assumes:

- Untrusted users may submit any text to `/api/chat`.
- Adversaries may attempt prompt-injection, jailbreaks, or PII exfiltration.
- Adversaries may attempt to use the chat surface to consume API budget
  (Gemini, Maps, YouTube quotas).
- Adversaries may attempt classic web attacks (XSS, CSRF, header injection).

## Defenses in place

### Application layer

| Control | Implementation |
|---|---|
| **Input validation** | Pydantic v2 strict schemas on every endpoint |
| **PII redaction** | Email, phone, Aadhaar, PAN stripped before LLM call |
| **Prompt-injection blocks** | Pattern-matched at input |
| **Partisan filter** | Refused on input *and* output |
| **LLM safety filters** | Gemini: `BLOCK_MEDIUM_AND_ABOVE` for harassment / hate / sexual / dangerous |
| **XSS prevention** | Server returns JSON; client `escapeHtml` before DOM injection |
| **Rate limiting** | slowapi: 30 req/min/IP (configurable) |
| **CORS** | Explicit allow-list (`ALLOWED_ORIGINS` env var) |

### Transport / headers

| Header | Purpose |
|---|---|
| `Strict-Transport-Security` | Force HTTPS for 1 year |
| `Content-Security-Policy` | Restrict script/style/img sources |
| `X-Content-Type-Options: nosniff` | Block MIME-sniffing |
| `X-Frame-Options: DENY` | Clickjacking protection |
| `Referrer-Policy: strict-origin-when-cross-origin` | Limit referrer leak |
| `Permissions-Policy` | Disable mic/camera; allow geolocation only on self |

### Secrets

- API keys live in **Google Secret Manager** (never in code, image, or env).
- Cloud Run mounts secrets at runtime via the runtime service account.
- API keys carry **API-restriction** (only specific endpoints reachable).
- Rotation: regenerate in Cloud Console → push new version with
  `gcloud secrets versions add ...`. Cloud Run picks up `:latest` on next
  request — no redeploy needed.

### IAM

The Cloud Run service runs under a dedicated service account
`civicguide-runtime@...` with **only** these roles:

- `roles/secretmanager.secretAccessor` (for the 3 secrets only)
- `roles/cloudtranslate.user`
- `roles/aiplatform.user` (when Vertex AI backend is in use)

No human accounts can access the runtime context.

### Container

- Multi-stage build → minimal `python:3.11-slim` runtime image
- Runs as **non-root user**
- No SSH / shell exposed
- `--proxy-headers --forwarded-allow-ips="*"` to honour Cloud Run's
  TLS-terminating proxy

### Supply chain

- Pinned dependency versions in `requirements.txt`
- Dependabot (see `.github/dependabot.yml`) raises PRs for security
  updates weekly
- `pip-audit` recommended in CI (see `.github/workflows/ci.yml`)

## Responsible disclosure

We follow [coordinated disclosure](https://en.wikipedia.org/wiki/Coordinated_vulnerability_disclosure):

1. Reporter privately notifies maintainer.
2. Maintainer reproduces & develops a fix.
3. Both parties agree on a disclosure date.
4. Patch is released; reporter is credited (if they wish).

Thank you for helping keep CivicGuide safe for citizens.
