## Summary

<!-- One short paragraph: what changed and *why*. Link issues with #123. -->

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change (bumps major version)
- [ ] Documentation only
- [ ] Test / CI / tooling

## Checklist

- [ ] Tests added or updated for the change
- [ ] Docstrings on new public callables (Google style)
- [ ] OpenAPI metadata on new routes (`summary`, `description`, etc.)
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] Coverage didn't drop below 85% (`make cov` to check locally)
- [ ] No new `bandit` findings (`make lint`)
- [ ] No new dependencies without a clear justification

## Screenshots / curl output (if a UI or API change)

<!-- Paste before/after screenshots, or curl output. -->

## How to verify

```bash
# Steps a reviewer should run to verify the change.
make ci
```
