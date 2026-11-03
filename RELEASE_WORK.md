# 0.1.0 stable release

The 0.1.0 release promotes the validated 0.1.0rc2 code to the first stable package.

- [x] PostgreSQL TLS is explicit and certificate verification defaults on when TLS is enabled.
- [x] Worker leases, fencing, shutdown health, retry history, and housekeeping are hardened.
- [x] SQLite, PostgreSQL 17, and MySQL 8.4 migration/queue paths have automated coverage.
- [x] Docker covers non-root execution, persistent restart, delivery, and graceful stop.
- [x] PyPI metadata, stable version references, and the bundled console are aligned at 0.1.0.
- [x] PyPI and Docker installation, upgrade, preservation, and complete removal are documented.
- [x] Publication is gated on CI, distribution validation, and a matching signed-off version tag.

Credentialed third-party providers, Oracle, production reverse proxies, backup/restore, and
deployment-specific security controls remain subject to the documented support boundaries
and operator acceptance.
