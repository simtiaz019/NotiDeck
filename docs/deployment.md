# Deployment

For local use, install the wheel and run `notideck serve` then `notideck worker`.
For production, supervise these separately with your OS service manager:

```sh
notideck serve --host 127.0.0.1 --port 8000
notideck worker --concurrency 4  # PostgreSQL/MySQL; SQLite uses 1
```

Both processes need the same configuration and master encryption key. SQLite also needs
the same local database path. Do not put SQLite WAL databases on network filesystems.
Multiple SQL-backed workers use conditional claims. Local PostgreSQL 17/MySQL 8.4 tests
cover concurrent ingestion, competing claims, expired-lease recovery and recorded completion.

## Containers

The Dockerfile builds React assets and a wheel, then installs the package into a Python
3.12 slim image. The application runs as UID/GID 10001. Persistent `/data` stores the
configuration and, for SQLite, the database. Keep it private and backed up.

```sh
docker compose up --build -d web
# Retrieve bootstrap token privately and complete browser setup:
docker compose exec web cat /data/bootstrap.token
docker compose up -d worker
```

The default port is bound only to host loopback. For PostgreSQL:

```sh
export POSTGRES_PASSWORD='your-unique-database-password'
docker compose -f docker-compose.postgres.yml up --build -d postgres web
# Wizard: engine PostgreSQL, host postgres, port 5432,
# database notideck, user notideck, the password supplied above.
# This example PostgreSQL container has no TLS: uncheck Use TLS/SSL in the wizard.
docker compose -f docker-compose.postgres.yml up -d worker
```

The container includes PostgreSQL and MySQL extras; Oracle needs a derivative image
installing the Oracle extra. Compose web health checks verify process liveness, so setup
can start before readiness. Readiness at `/api/v1/health/ready` additionally checks schema,
database reachability and completed initialization. Worker health comes from persisted
heartbeats; stale records are shown as unhealthy, not silently reported alive.

The candidate image was built locally. `tests/docker_smoke.py` tests a disposable volume,
non-root execution, setup, persistent restart and real worker HTTP delivery.

## Reverse proxy and HTTPS

Use TLS at a trusted reverse proxy. The Nginx location example is in `docs/nginx.conf`.
The default CLI does not trust forwarded headers. Behind TLS termination, use an ASGI
server with an explicit trusted proxy address list, for example:

```sh
NOTIDECK_SECURE_COOKIES=1 uvicorn notideck.api:create_app --factory \
  --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=127.0.0.1
```

Pass the original Host and HTTPS scheme. Do not trust arbitrary `X-Forwarded-For` headers
from public clients; source network policies and login rate limits depend on trustworthy
peer information. Configure TLS certificates, HSTS, restricted admin access, body limits,
firewalling and host validation at the proxy. Console and API must share an origin.

Keep HTTP egress blocked to internal/metadata networks except explicit trusted integration
allowlists. SMTP hosts and installed Python plugins require separate trusted egress policy.
Keep the master key outside the database and back it up separately with restricted access.

## Operations

Back up database and key/config together. For SQLite, stop writers or use SQLite's online
backup API; do not copy only the main file while WAL writes are active. Use native logical
or physical backup tools for external databases. Test restore before upgrades.

Run `notideck db migrate` during a controlled maintenance window. Startup never silently
resets a database. Failed readiness should trigger investigation, not automatic recreation.
Retention supports administrator preview/confirmation in 500-event batches. Automatic
retention defaults off; enable `retention_enabled` in Settings to run one batch hourly while
a worker is running. Expired sessions and stale worker/rate-limit records are cleaned
automatically in bounded batches regardless of retention enablement. Audit records are
not deleted by notification retention. Graceful container stop allows 45 seconds; longer
custom plugin calls can exceed this and be recovered later via the lease.
