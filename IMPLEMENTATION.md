# Implementation and acceptance checklist

## Milestones

- [x] M1: Python package, CLI, FastAPI, portable ORM, WAL SQLite, frozen Alembic migration.
- [x] M2: protected restart-safe setup, database connection test, administrator, sessions,
  CSRF, password changes/reset, fixed-role backend RBAC and login rate limits.
- [x] M3: sources, scoped/expiring/revocable keys, signed ingestion, transactional routing,
  idempotency, durable queue, conditional claims, leases, retries and audit history.
- [x] M4–5: eight actual provider transports, encrypted configurations, tests and plugins.
- [x] M6 operational Console: setup, dashboard/history, queue, channels, rules, sources,
  recipients/groups/templates, users, audits/settings, polling and themes.
- [x] M7 local verification: SQLite concurrency, security, provider and schema compilation tests.
- [ ] M7 external verification: execute PostgreSQL/MySQL CI and Oracle integration suite.
- [x] M8 artifacts: bundled frontend/docs/templates/migrations, wheel/sdist, examples,
  deployment definitions, CI/release workflows, clean-wheel delivery smoke test.
- [ ] M8 release readiness: Docker runtime validation, provider credentials testing,
  security/scale review and maintainer-configured publishing approvals.

The broad milestone checks describe delivered working functionality, not every detailed
sub-requirement. Product gaps are explicitly listed in docs/limitations.md.

## Acceptance evidence

| Original criterion | Implementation / verification |
| --- | --- |
| 1 Install built wheel | Clean temporary virtual environment passed |
| 2 Start CLI server | Real subprocess from outside repository passed |
| 3 SQLite setup wizard | Full browser flow passed |
| 4 Administrator/login | API and browser tests passed |
| 5 Configure channels | Browser + API tests passed |
| 6 Configure routing | Browser + matching tests passed |
| 7 Authenticated external event | Browser request + wheel smoke passed |
| 8 Persist event | API and wheel smoke passed |
| 9 Route destinations | Condition, priority, group and overlap tests passed |
| 10 Worker delivery | Separate installed worker sent to real local receiver |
| 11 Record attempts/failures | Provider and worker tests passed |
| 12 Retry/dead letters | Transient/permanent error and manual retry tests passed |
| 13 Console history | Browser flow passed |
| 14 Console queue | Browser flow passed |
| 15 Authorized queue clear | Preview, permission, cancellation/history tests passed |
| 16 Permissions | Viewer/operator/admin, CSRF and session tests passed |
| 17 Document API/webhooks | Local Swagger bundle, generated schema, docs/examples |
| 18 Channel tests | Real adapter test-send path; mocked provider verification |
| 19 Package metadata/assets | Build, twine, archive inspection and clean install passed |
| 20 Available automated environments | See docs/validation.md for actual results |
| 21 Docker deployment starts | NOT verified: daemon unavailable |
| 22 Trusted Publishing workflow | OIDC workflow authored; hosting approvals not configured |
| 23 No default credentials | Random bootstrap token; user-created admin; synthetic test fixtures only |
| 24 Accurate README | Alpha label, working flow, known gaps and unverified environments documented |
