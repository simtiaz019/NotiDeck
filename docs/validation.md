# Release candidate validation

Local execution on **2026-10-26**, macOS, Python 3.12, Node 26, Docker Desktop.
Candidate: **0.1.0rc1**, schema revision **0002**. These are local results, not remote CI results.

| Check | Actual result |
| --- | --- |
| Backend and SQLite integration | 90 passed, 2 skipped (the two external-DB cases run separately below) |
| Python lint / type checking | Ruff passed; mypy passed (19 source files) |
| Frontend production build | TypeScript/Vite passed; bundled assets updated |
| Frontend components | 4 passed |
| Real browser workflow | 1 passed: setup, login, configuration, ingestion, history and cancellation |
| PostgreSQL 17 live integration | 8 passed: migration, idempotency race, competing claims, lease recovery, fractional timestamps, Unicode and attempt/aggregate completion |
| MySQL 8.4 live integration | Same 8 tests passed after fixing single-precision epoch timestamps |
| SQLite upgrade | Revision 0001 to 0002 preserves an existing record; current-schema detection verified |
| Wheel/sdist and metadata | Both 0.1.0rc1 archives built; twine checks passed |
| Clean installed wheel | Passed in a fresh venv: bundled UI, setup/login, real worker delivery and cancellation |
| Archive inspection | UI, migration 0002 and template library present; no virtualenv, node_modules or application key/token files |
| Docker build | Candidate image built successfully, UID/GID 10001 |
| Docker delivery and restart | Passed: fresh setup, persistent queued event after restart, real local HTTP transport, attempt history, graceful shutdown heartbeat |
| Python dependency audit | pip-audit: no known vulnerabilities after updating filelock and pip |
| Frontend dependency audit | npm audit: zero vulnerabilities, including dev dependencies |

Reproduction commands (set `PYTHONPATH=src` if the active environment contains an older installed wheel):

```sh
ruff check src tests
mypy src/notideck
pytest -q
npm --prefix frontend ci
npm --prefix frontend run build
npm --prefix frontend test
python tests/browser_smoke.py
python -m build
python -m twine check dist/notideck-0.1.0rc1*
python tests/wheel_smoke.py
docker build -t notideck:rc-test .
python tests/docker_smoke.py
```

For live database tests use the disposable `tests/docker-compose.integration.yml` stack
and set `NOTIDECK_TEST_DATABASE_URL` to that test database before running
`pytest tests/test_database.py tests/test_external_queue.py`. Never point these tests at
production. Docker smoke creates and removes only its uniquely named test containers/volume.

User acceptance evidence: the original 0.1.0 CSV has 49 Pass and 16 Not tested entries.
The user confirmed email and Telegram delivery. Those results are preserved; no untested
provider was promoted to a live pass. Candidate regression acceptance remains a user task.

One upstream Starlette TestClient deprecation warning remains. Oracle, verified PostgreSQL
TLS against a certificate-equipped server, the Windows/Python version CI matrix, production
reverse proxy configuration and load/soak testing have not been verified locally. Remote
CI, PyPI/TestPyPI ownership and publication have not been performed. See limitations.md.
