# Development and validation

Use Python 3.11+ (implementation tested locally on 3.12) and Node 22.12+.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
npm --prefix frontend ci
npm --prefix frontend run build
pytest --cov=notideck
npm --prefix frontend test
ruff check src tests
mypy src/notideck
python -m build
python tests/wheel_smoke.py
```

`requirements-dev.lock` records the tested Python environment. To reproduce it on a
compatible platform, install that file and then `pip install --no-deps -e .`. The published
wheel intentionally declares compatible ranges, not a mandatory global environment lock.
The frontend uses npm's package-lock for transitive reproducibility.

Browser tests launch an isolated, temporary fresh installation:

```sh
cd frontend && npx playwright install chromium && cd ..
python tests/browser_smoke.py
# Use installed Chrome instead when available:
NOTIDECK_BROWSER_CHANNEL=chrome python tests/browser_smoke.py
```

They complete browser setup/login, create channel/rule/source/key, submit an event,
inspect history and cancel queued work. A generated screenshot is test evidence, not
seeded production data. The clean-wheel smoke test uses another new venv and working
directory, a real local HTTP receiver, a server subprocess and a separate worker subprocess.
It verifies durable ingestion, actual transport, recorded acceptance and safe cancellation.

Provider unit tests use HTTPX MockTransport and fake SMTP; no credentials are needed.
Concurrency tests race SQLite claims. External integration tests can run against a
**dedicated disposable database**:

```sh
pip install -e '.[dev,postgres]'
NOTIDECK_TEST_DATABASE_URL='postgresql+psycopg://user:password@localhost/testdb' \
  pytest tests/test_database.py tests/test_external_queue.py
```

The same tests accept mysql+pymysql and oracle+oracledb URLs with installed extras. They
run migrations, portable JSON roundtrips, concurrent idempotency and job claims, and lease
recovery. They create/delete test records; do not point them at production. CI provisions
PostgreSQL/MySQL. Oracle remains optional and unverified without credentials/service.

Structure:

- `src/notideck/api`: API transport, dependencies and endpoint RBAC
- `database/models.py`: portable ORM models; `migrations/`: frozen schema revisions
- `services.py`: transactional ingestion, routing expansion and aggregate status
- `routing.py`: conditions and restricted template rendering
- `worker.py`: claims, retries, throttling, leases and process supervision
- `providers/`: provider protocol, registry and built-in adapters
- `security.py`, `config.py`: hashing, rate limits, transport protection and secure config
- `frontend/src`: React Console, API client and styles
- `tests/`: backend, provider, integration, browser and wheel validation

Frontend development: `npm --prefix frontend run dev` proxies `/api` to localhost:8000.
Cookie authentication requires same-origin requests; the Vite proxy preserves the browser
origin, so use the production bundle for security-sensitive flows until a dedicated dev
origin configuration is added. Rebuild assets before packaging. Do not edit generated
static bundles directly. Plugins and migrations need explicit compatibility reviews.
