# Changelog

## 0.1.0rc1 — 2026-10-26

Production release candidate; final maintainer acceptance and publication pending.

- PostgreSQL setup now explicitly supports TLS on/off, with certificate and hostname verification by default when enabled.
- Renew active worker leases, fence expired completions, record undecryptable credentials as failures, and mark stopped workers unhealthy.
- Correct MySQL epoch timestamp precision using migration 0002 and double precision columns.
- Add opt-in automatic retention and bounded expired-session/rate-limit/worker cleanup. Preserve audit history and active deliveries.
- Queue cancellation/retry respects the visible status filter; validate password changes, previews, timezone and retention inputs.
- Raise the filelock minimum to the audited patched series; remove the Docker wheel version hardcode.
- Gate release on the full CI matrix, live database checks, browser workflow and real Docker delivery smoke.

## 0.1.0 — original local alpha (not published)

- Verify the bootstrap token on the Welcome step before database configuration. Trim
  surrounding whitespace and distinguish setup tokens from source API keys in errors.

- Add five database alert templates, an editable audit-event example, and template
  selection by name in the routing editor. Fresh setup installs the template library;
  existing installations can add missing templates without overwriting edits.

- Correct SMTP error classification: recipient/relay rejections and SMTP response codes
  are preserved instead of being reported as generic transport timeouts. Provider
  response text and recipient addresses remain redacted.

Initial alpha implementation: setup, Console, authenticated event ingestion,
routing, durable delivery queue, eight provider adapters, RBAC, packaging,
deployment examples and automated tests. See docs/limitations.md for release gaps.
