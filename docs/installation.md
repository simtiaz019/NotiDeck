# Installation

Requires Python 3.11+. Build a distribution with `npm --prefix frontend ci`,
`npm --prefix frontend run build`, and `python -m build`; install the wheel using
`pip install dist/notideck-0.1.0-py3-none-any.whl`. A published wheel will need no
Node runtime. The project has not been published to PyPI by this implementation.

Run `notideck serve`. It binds to 127.0.0.1:8000, prints the Console URL and the
private bootstrap token file path (not the token). Open the Console, read the token
locally, and complete Welcome → Database → Administrator → Application → Finish.
The first administrator is stored in the selected database. Login after initialization.

The default data directory uses platformdirs: typically
`~/Library/Application Support/notideck` on macOS, `~/.local/share/notideck` on
Linux, or the current user's application data directory on Windows. Override with
`NOTIDECK_CONFIG_DIR` and `NOTIDECK_DATA_DIR`.

Start `notideck worker` in a second terminal. Alternatively, after setup, restart
with `notideck serve --embedded-worker`. This is a single CLI-managed child process,
not an ASGI startup hook. Running `create_app()` under another process manager does
not start workers automatically. Supervise separate web and worker processes in production.

Optional drivers:

```sh
pip install 'notideck[postgres]'  # psycopg 3
pip install 'notideck[mysql]'     # PyMySQL
pip install 'notideck[oracle]'    # python-oracledb
pip install 'notideck[all]'
```

For an unpublished build, use `pip install './dist/notideck-0.1.0-py3-none-any.whl[postgres]'`.

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

Set mode 0600 and run `notideck init /private/path/setup.json`. The file's values
are supplied by you, not built-in credentials. Remove the file securely afterward.
Setup is one-time and refuses initialized databases. The local configuration is saved
before committing initialization so a crash can reconnect. Schema DDL is not
transactional on every database; partially applied initial migrations are restartable,
but no cross-filesystem/database distributed transaction is claimed.
