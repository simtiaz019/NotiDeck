# Upgrade to 0.1.0rc1

This candidate is ready for your acceptance testing. Nothing has been published to PyPI.
Keep your original 0.1.0 validation CSV; record new results separately. Email and Telegram
are user-confirmed, while the other credentialed providers still need live acceptance.

## Existing Docker installation

Run from the same checkout directory and Compose project used for your current installation.
Do not change project/volume names. Build before stopping the current deployment:

```sh
docker compose build
# Stop writers before backing up or migrating:
docker compose stop worker web
```

Back up the entire existing `/data` directory (including `master.key`, `config.json`,
SQLite files and any WAL/SHM files) to a restricted directory. This works with a stopped
web container; choose a new, private destination:

```sh
mkdir -m 700 ./backup-before-0.1.0rc1
docker compose cp web:/data/. ./backup-before-0.1.0rc1/
chmod -R go-rwx ./backup-before-0.1.0rc1
```

If using external PostgreSQL/MySQL, also take and verify a database-native backup.
The `/data` backup alone does not contain an external database. If your encryption key
comes from an environment secret, preserve that secret separately. Never commit backups.

```sh
docker compose run --rm --no-deps web db migrate
docker compose run --rm --no-deps web doctor
docker compose up -d web worker
docker compose ps
```

If you use `docker-compose.postgres.yml`, use the same `-f docker-compose.postgres.yml`
option on every command and leave PostgreSQL running for migration. Do not run setup again
on an existing installation. Your users, keys, channels and templates remain in the database.
Do not use `down -v`: that removes persistent data.

Migration 0002 fixes MySQL timestamp precision. Existing rounded timestamps cannot recover
lost precision. SQLite data stays in place; all engines advance their schema revision.
Old binaries should not be run against the upgraded database.

## Wheel installation

Stop web and worker processes, back up data/config/key as above, then use your application
virtual environment (include the appropriate extra for an external database):

```sh
python -m pip install --upgrade 'dist/notideck-0.1.0rc1-py3-none-any.whl[postgres,mysql]'
notideck db migrate
notideck doctor
notideck serve
# In a second terminal using the same configuration:
notideck worker
```

If you used `--config` or environment variables previously, use the same values throughout.

## Final acceptance

1. Confirm version `0.1.0rc1` and successful readiness/doctor checks after migration.
2. Sign in with your existing account; verify sources, keys, channels, routes and templates.
3. Send a uniquely identified event through your source key to both email and Telegram.
   Confirm actual receipt, rendered template and the recorded attempt in the Console.
4. Repeat the same idempotency key/payload: no duplicate jobs. Change its payload: conflict.
5. Pause dispatch, enqueue, restart web/worker, resume and confirm the event is delivered.
6. Exercise failure/retry/dead-letter and filtered cancellation against test destinations.
7. Confirm PostgreSQL connects with TLS unchecked for your non-TLS server. Verified TLS
   requires certificates and a matching hostname; that deployment-specific test is separate.
8. Check your reverse proxy HTTPS, secure cookies, backups and restore procedure.
9. Leave automatic retention off unless you intend to delete aged terminal history.

See [release gates](release.md) before publishing. After candidate acceptance, promote all
version references to `0.1.0`, rebuild frontend and distributions, and rerun CI and clean-wheel
smoke. Do not rename an RC wheel to make it a stable wheel.

## Rollback

Stop writers. Restore the pre-upgrade database and its matching configuration/encryption key,
then run the saved pre-upgrade wheel/image. Verify restore in isolation first. There is no
lossy automatic downgrade for migration 0002. Events created after the backup need separate
reconciliation; rolling back a backup does not preserve them automatically.
