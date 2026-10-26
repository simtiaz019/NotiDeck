# Configuration and database support

| Variable | Purpose |
| --- | --- |
| NOTIDECK_CONFIG_DIR | Private config, bootstrap token and local master key directory |
| NOTIDECK_DATA_DIR | Default SQLite database directory |
| NOTIDECK_MASTER_KEY | External Fernet key; overrides locally generated key |
| NOTIDECK_DATABASE_URL | SQLAlchemy URL; overrides encrypted saved URL |
| NOTIDECK_SECURE_COOKIES | `1` forces Secure cookies; required behind TLS termination |
| NOTIDECK_PASSWORD_MIN_LENGTH | Password minimum, never below 12 |
| NOTIDECK_OUTBOUND_ALLOW_NETWORKS | Comma-separated trusted CIDRs for internal HTTP destinations |
| NOTIDECK_TEST_DATABASE_URL | Dedicated disposable DB for optional integration tests |

Use environment secrets or secret files managed outside version control. When setting
a SQLAlchemy URL manually, percent-encode special characters in passwords. The wizard
uses `URL.create`, so password characters entered there are handled correctly.

The UI stores application name, base URL, display time zone, retention days, maximum
attempts and base retry delay in the database. Provider timeout is 1–30 seconds.
Worker concurrency is a process/CLI setting, not a dynamically resized pool.
Database connection settings cannot be changed through the initialized public setup API.

## Database targets

| Engine | Target minimum | Driver | Queue behavior | Local verification |
| --- | --- | --- | --- | --- |
| SQLite | 3.35+ | stdlib sqlite3 | Conditional claim, WAL, one worker recommended | Full automated flow |
| PostgreSQL | 14+ | psycopg 3 | SKIP LOCKED plus conditional fencing | DDL compilation only; live service unavailable |
| MySQL | 8.0+ with InnoDB | PyMySQL | SKIP LOCKED; READ COMMITTED | DDL compilation only; live service unavailable |
| Oracle | 19c+ target | python-oracledb thin mode | Portable conditional claim fallback | DDL compilation only; live service unavailable |

Target versions are engineering targets, **not a certified compatibility matrix**.
The CI definitions provision PostgreSQL 17 and MySQL 8.4. An Oracle integration run is
optional via environment variable; Oracle validation remains incomplete.

All app tables use `nd_` prefixes. IDs are 36-character UUID strings; timestamps are
UTC Unix seconds; structured JSON is encoded in portable TEXT/CLOB columns. Optional
empty text fields are nullable because Oracle treats empty strings as NULL. The initial
migration has frozen table declarations. Future changes need new migrations.

Database accounts need SELECT/INSERT/UPDATE/DELETE on application tables and appropriate
DDL privileges during migrations. Connection testing verifies reachability; migration
application verifies DDL privilege in practice. The application does not create external
PostgreSQL/MySQL databases or Oracle schemas. Provision those first. PostgreSQL accepts an optional schema_name in setup (simple SQL identifier, pre-created
with appropriate grants), or uses the connection's default search path. Schema names are
restricted to letters/digits/underscores and are not interpolated into SQL statements.
Dedicated role/database configuration is recommended.
Oracle uses the account owner's schema. MySQL connects to the named preexisting database.
There is no cross-database CREATE SCHEMA operation.

Do not place an unrelated `alembic_version` table or preexisting `nd_*` tables in the
same schema. A mismatched migration revision fails closed. Existing unrelated tables
are not deleted. Back up the database and encryption key together before upgrades, then
run `notideck db status`, `notideck db migrate`, and `notideck doctor`.
