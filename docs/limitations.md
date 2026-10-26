# Implementation limits and release blockers

Version **0.1.0rc1** is a production release candidate, not completion of every item
in the original specification. SQLite, PostgreSQL 17 and MySQL 8.4 have local automated
integration coverage. Email and Telegram were confirmed by the user in the alpha checklist.
The remaining scope below is explicit; a release candidate is not an independent security certification.

## Support and verification boundaries

- Oracle: schema compiles for its SQLAlchemy dialect, but no Oracle service was available.
  The queue uses conditional claims, not Oracle SKIP LOCKED. Driver/version compatibility,
  CLOB handling and Oracle migration behavior need actual integration verification.
- Docker: an isolated non-root image smoke test covers setup, persistent restart, queue delivery
  to a real local HTTP receiver and graceful worker shutdown. This is not a load/soak test.
- SMTP and Telegram: user-confirmed delivery. Slack, Discord, WhatsApp, Twilio and Signal
  have adapter tests but no live credentialed acceptance in this session. Webhook HTTP
  transport is exercised locally; production endpoints need acceptance testing.
- Python/OS matrix: local execution is Python 3.12 on macOS; CI defines 3.11–3.13 and
  Windows/macOS/Linux jobs, but remote CI has not been run from this unhosted repository.
- PyPI/TestPyPI publication and ownership, GitHub environment protection, repository URLs
  and security reporting contacts require actual maintainer configuration.

## Product gaps compared with the full specification

- WhatsApp/provider delivery receipt callbacks and recipient-confirmed states are absent.
  SENT explicitly means provider acceptance, not delivered/read confirmation.
- Roles are fixed workspace-wide permission sets; configurable per-resource grants,
  custom role management, separate permission tables and channel subscriptions are absent.
- Environments are strings, not independently managed environment entities. Recipient
  group memberships and rule targets use validated JSON references instead of relational
  membership/target join tables. Deletion APIs are deliberately limited to avoid orphaning.
- Queue API offers channel/source/severity/age filters and channel backlog/worker metrics.
  Console currently exposes environment/status filters and individual selections, but
  dedicated source/channel/age filter controls and detailed worker/backlog tables are missing.
- The dashboard provides persisted counts, latest events and severity distribution; it
  lacks time-series charts, latency percentiles, per-source analytics and per-channel health
  charts. Notification detail shows all deliveries for one event without pagination.
- Rule forms support all conditions and channel selection, with advanced JSON targets.
  Group/template linking is not yet a polished multi-step route wizard. Up to 100 channel
  or recipient choices are loaded in selectors; larger catalogs need a searchable selector.
- Explicit duplicate fan-out is not supported; first matching channel/recipient is deduplicated.
- SMTP supports To/CC/BCC, but partial acceptance is one channel-level result, not a separate
  job per SMTP envelope recipient. Provider address/message length validation is not exhaustive.
- Webhook payloads and WhatsApp template components support restricted interpolation;
  there are no rich provider-specific template editors or template localization.
- Provider-specific HTTP error handling is present, but global API/account-level quotas
  shared by multiple channel instances are not modeled. Spacing is per channel.
- Worker concurrency is configured at process startup. Leases renew during long-running
  calls; expired owners cannot commit completion. Automatic retention is opt-in and processes
  up to 500 old terminal events hourly. Housekeeping also cleans expired sessions and stale
  rate buckets/workers in bounded batches. Large backlogs can require manual batches.
- Audit records capture safe mutation summaries, not a complete old/new diff for every field.
  Audit export, tamper evidence, dedicated scrape-token auth and richer observability are absent.
- Migration privilege preflight is limited: connection testing is read-only; actual migration
  application verifies DDL permissions. External databases/schemas must be provisioned first.
- Encryption-key re-encryption/rotation tooling is absent. SMTP does not use HTTP SSRF
  restrictions; deployment egress controls remain necessary. Plugin code is administrator-trusted.
- Independent security review, accessibility audit, load/soak testing, failure injection across
  real external databases and production operations exercises remain release gates.

These gaps must not be described as implemented production features. See
[release checklist](release.md) for the explicit publication gates. No package was published.
