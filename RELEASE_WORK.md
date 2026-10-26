# 0.1.0rc1 production release candidate

Candidate implementation completed; user acceptance/publication remains separate.
No production database was migrated and no package was published.

- [x] PostgreSQL TLS checkbox: explicit disabled or certificate-verified default
- [x] Active lease renewal, expired-owner fencing, worker shutdown health, invalid-credential failure history
- [x] Bounded housekeeping and opt-in automatic retention preserving active jobs/audits
- [x] Queue visible-status action consistency and administrator request validation
- [x] Live isolated PostgreSQL 17 / MySQL 8.4 migration, concurrency and completion checks
- [x] MySQL timestamp precision fix and SQLite upgrade preservation test
- [x] Docker fresh setup, real worker delivery, restart persistence and graceful stop
- [x] Dependency audits, backend/frontend/browser validation
- [x] Candidate versioning and version-independent Docker wheel installation
- [x] Release workflow full CI gate, support boundaries and upgrade/rollback instructions

Final package artifact checks are recorded in docs/validation.md. Detailed queue source/channel/age
controls and worker/backlog tables remain product-scope limitations, not advertised as completed.
Public repository URLs/security contact, remote CI matrix, final deployment acceptance and
publication are maintainer steps in docs/release.md.
