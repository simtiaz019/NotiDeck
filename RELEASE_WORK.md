# 0.1.1 logging patch release

The 0.1.1 release adds persistent, private diagnostic logs for the server and worker.

- [x] PostgreSQL TLS is explicit and certificate verification defaults on when TLS is enabled.
- [x] Worker leases, fencing, shutdown health, retry history, and housekeeping are hardened.
- [x] SQLite, PostgreSQL 17, and MySQL 8.4 migration/queue paths have automated coverage.
- [x] Docker covers non-root execution, persistent restart, delivery, and graceful stop.
- [x] PyPI metadata, stable version references, and the bundled console are aligned at 0.1.0.
- [x] PyPI and Docker installation, upgrade, preservation, and complete removal are documented.
- [x] Publication is gated on CI, distribution validation, and a matching signed-off version tag.
- [x] Server and worker write separate 10 MiB rotating logs with five backups.
- [x] Setup accepts an optional absolute shared log directory and provides a secure default.
- [x] Existing installations receive default logs without a database migration and can override the path.

Credentialed third-party providers, Oracle, production reverse proxies, backup/restore, and
deployment-specific security controls remain subject to the documented support boundaries
and operator acceptance.
