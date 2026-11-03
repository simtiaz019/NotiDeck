# Installation and removal

NotiDeck requires Python 3.11 or newer. The PyPI package includes the web console, so
Node.js is not required unless you build from source. SQLite is included and is the
simplest option for a local installation.

## Install from PyPI

Use a dedicated virtual environment so NotiDeck and its dependencies are isolated from
the system Python.

### macOS and Linux

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install notideck
notideck --version
```

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install notideck
notideck --version
```

Install the extra for an external database if needed:

```sh
python -m pip install "notideck[postgres]"  # PostgreSQL / psycopg 3
python -m pip install "notideck[mysql]"     # MySQL / PyMySQL
python -m pip install "notideck[oracle]"    # Oracle / python-oracledb (experimental)
python -m pip install "notideck[all]"       # All optional database drivers
```

### Complete first-run setup

Start the web server while the virtual environment is active:

```sh
notideck serve
```

Open <http://127.0.0.1:8000>. The terminal shows the path to the private
`bootstrap.token` file. Read that file locally, paste the token into the setup wizard,
choose the database, and create the first administrator. The token is not a source API key
and must not be shared.

The default configuration/data directory is usually:

- macOS: `~/Library/Application Support/notideck`
- Linux: `~/.local/share/notideck`
- Windows: the `notideck` folder under the user's local application-data directory

`NOTIDECK_CONFIG_DIR` and `NOTIDECK_DATA_DIR` override these locations. The
`notideck doctor` command prints the effective configuration directory and verifies the database.

### Start notification delivery

The API queues notifications; a worker sends them. Keep the server running, open a second
terminal, activate the same virtual environment, and run:

```sh
notideck worker
```

For a small local installation, you can instead stop the server after setup and restart
both components from one command:

```sh
notideck serve --embedded-worker
```

Production installations should supervise separate `notideck serve` and `notideck worker`
processes. See [deployment](deployment.md).

### Upgrade a PyPI installation

Back up the database, configuration directory, and encryption key together. Then activate
the virtual environment and run:

```sh
python -m pip install --upgrade notideck
notideck db migrate
notideck doctor
```

Include the same database extra used for the original installation, for example
`python -m pip install --upgrade "notideck[postgres]"`.

## Install with Docker Compose

Docker Engine with the Compose plugin and Git are required. The default Compose stack
builds the image locally, binds the console to `127.0.0.1:8000`, and stores configuration,
the encryption key, and the SQLite database in the `notideck-data` named volume.

```sh
git clone https://github.com/simtiaz019/NotiDeck.git
cd NotiDeck
docker compose up --build -d web
docker compose exec web cat /data/bootstrap.token
```

Open <http://127.0.0.1:8000>, enter the displayed bootstrap token, and complete the
wizard. Then start the worker:

```sh
docker compose up --build -d worker
docker compose ps
```

Do not run `docker compose down -v` during normal operation: `-v` deletes the named data
volume and the SQLite installation stored in it.

For the included PostgreSQL example, set a strong password and use the alternate Compose
file:

```sh
export POSTGRES_PASSWORD='replace-with-a-unique-password'
docker compose -f docker-compose.postgres.yml up --build -d postgres web
docker compose -f docker-compose.postgres.yml exec web cat /data/bootstrap.token
```

In the wizard, use host `postgres`, port `5432`, database/user `notideck`, and the password
above. The example database does not enable TLS, so leave **Use TLS/SSL** unchecked. After
setup, start the worker:

```sh
docker compose -f docker-compose.postgres.yml up -d worker
```

### Upgrade a Docker installation

Back up the database and `/data` volume first. From the cloned repository:

```sh
git pull --ff-only
docker compose build --pull
docker compose up -d web worker
docker compose exec web notideck db migrate
docker compose exec web notideck doctor
```

Use `-f docker-compose.postgres.yml` on every Compose command if that is how the stack was
started.

## Uninstall a Python installation

First stop `notideck serve` and every `notideck worker` process. Before removing anything,
run `notideck doctor` and record the displayed configuration directory.

With the installation's virtual environment active:

```sh
python -m pip uninstall notideck
```

This removes the package only. It intentionally preserves configuration, the master
encryption key, SQLite data, and history so the installation can be restored. If the
virtual environment was dedicated to NotiDeck, deactivate it and delete that `.venv`
directory after confirming its path.

To erase the installation permanently, first make a verified backup if any data may be
needed. Then delete the exact configuration and data directories reported/configured for
this installation. If PostgreSQL, MySQL, or Oracle was used, package removal does not
delete that external database or database user; remove them separately only when you are
certain no other application uses them.

## Uninstall a Docker Compose installation

From the same repository directory, stop and remove the containers while preserving all
persistent data:

```sh
docker compose down --remove-orphans
```

That is the recommended reversible uninstall. The `notideck-data` volume remains and can
be reused by running `docker compose up --build -d` again.

For a complete, irreversible removal of the default SQLite stack—including its database,
configuration, encryption key, containers, locally built images, and named volume—make a
verified backup and then run:

```sh
docker compose down --volumes --rmi local --remove-orphans
```

For the PostgreSQL example, use the same command with `-f docker-compose.postgres.yml`.
This also deletes the Compose-managed PostgreSQL volume. Compose does not delete external
databases, bind-mounted host directories, or manually supplied secrets. Afterward, the
cloned repository directory can be deleted if it contains no backups or local changes.

## Unattended setup

Create a private JSON file matching `SetupInput` in the OpenAPI schema. For example:

```json
{
  "database": {"engine": "sqlite"},
  "username": "your-admin-name",
  "full_name": "Your Administrator",
  "email": "your-address@example.com",
  "password": "REPLACE-WITH-A-UNIQUE-STRONG-PASSWORD",
  "confirm_password": "REPLACE-WITH-A-UNIQUE-STRONG-PASSWORD"
}
```

Set its permissions to `0600` on Unix-like systems and run:

```sh
notideck init /private/path/setup.json
```

Remove the file securely afterward. Setup is one-time and refuses an initialized database.
