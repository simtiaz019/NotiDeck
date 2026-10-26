# NotiDeck

**One platform. Every notification.**

Send an event once. Route it to the right channels. Track every delivery attempt.

NotiDeck is a self-hosted notification hub for application events, database alerts,
and operational messages. Manage your sources, channels, templates, and delivery queue
from a web console, with your data stored in your own database.

[Get started](#quick-start) · [Documentation](https://github.com/simtiaz019/NotiDeck/tree/main/docs) · [GitHub](https://github.com/simtiaz019/NotiDeck) · [Report an issue](https://github.com/simtiaz019/NotiDeck/issues)

**Release status:** NotiDeck is currently a pre-release. Install with `--pre` and review
[deployment guidance](https://github.com/simtiaz019/NotiDeck/blob/main/docs/deployment.md)
before using it in production.

## Quick start

You need **Python 3.11 or newer**. The installed package includes the web console;
Node.js is only needed when building from source. SQLite is the simplest way to try it.

**1. Install in a virtual environment**

```sh
python -m venv .venv
```

Activate it on macOS/Linux with `source .venv/bin/activate`, or in Windows PowerShell
with `.venv\Scripts\Activate.ps1`. Then install and start NotiDeck:

```sh
python -m pip install --pre notideck
notideck serve
```

**2. Complete browser setup**

Open **http://127.0.0.1:8000**. The terminal prints the location of your private
`bootstrap.token` file. Copy its contents into the setup wizard, choose your database,
and create your administrator account. Keep this token private; it is different from a source API key.

**3. Start delivery processing**

In a second terminal, activate the same virtual environment and run:

```sh
notideck worker
```

Leave both processes running: the server receives events and serves the console;
the worker sends queued notifications.

## What you can do

- **Connect your applications:** submit events using source API keys or signed webhooks.
- **Choose who gets notified:** route by severity, environment, tags, or event metadata.
- **Make alerts readable:** use templates for database errors, replication lag, backups, and more.
- **Keep track of delivery:** inspect attempts, retries, failures, and queued notifications.
- **Stay in control:** pause dispatch, retry failed jobs, and cancel pending jobs from the console.

## How it works

![Notification flow: your application sends an event to NotiDeck, routing rules select channels, a persistent queue holds deliveries, and workers send them to email, chat, or webhook destinations.](https://raw.githubusercontent.com/simtiaz019/NotiDeck/main/docs/images/notification-flow.png)

1. Your application submits an event with a title, message, severity, and optional metadata.
2. NotiDeck matches your routing rules and saves the notification and delivery jobs.
3. A worker sends each delivery and records the result. Retryable failures are rescheduled.

## Send your first notification

In the console:

1. Add a **Channel**, configure its credentials, and use **Test** to check delivery.
2. Add a **Routing rule** targeting that channel. For this example, match
   `environment equals production` and `severity gte ERROR`.
3. Add a **Source** and create its API key. Copy the key when it is displayed.
4. Submit an event and open **Notifications** to inspect the result.

Example for macOS/Linux:

```sh
export NOTIDECK_API_KEY='replace-with-your-source-api-key'

curl -X POST http://127.0.0.1:8000/api/v1/notifications \
  -H "Authorization: Bearer $NOTIDECK_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "environment": "production",
    "severity": "ERROR",
    "title": "Database replication lag",
    "message": "Replication lag exceeded 120 seconds.",
    "idempotency_key": "replication-alert-001"
  }'
```

A `202` response means the event was saved. A delivery marked `SENT` means the provider
accepted it; it does not confirm that the recipient read or received it. Delivery is
at least once, so a crash after provider acceptance can cause a duplicate send.

## Channels and databases

| Channel | Verification so far |
| --- | --- |
| Email (SMTP), Telegram | Live delivery confirmed during user testing |
| HTTP webhook | Real HTTP delivery covered by automated smoke tests |
| Slack, Discord, WhatsApp templates, Twilio SMS, Signal bridge | Adapters included; live account testing still needed |

See [channel setup](https://github.com/simtiaz019/NotiDeck/blob/main/docs/channels.md)
for provider requirements and configuration.

| Database | Installation |
| --- | --- |
| SQLite | Included; use one worker thread and local storage |
| PostgreSQL | `python -m pip install --pre "notideck[postgres]"` |
| MySQL | `python -m pip install --pre "notideck[mysql]"` |
| Oracle | Experimental; see the [support boundaries](https://github.com/simtiaz019/NotiDeck/blob/main/docs/limitations.md) |

PostgreSQL setup includes a TLS/SSL switch. Leave it unchecked for a server that does
not use TLS. When enabled, certificate and hostname verification is the default.

## Prefer Docker?

Docker Compose runs the server and worker with a shared persistent data volume.

```sh
git clone https://github.com/simtiaz019/NotiDeck.git
cd NotiDeck
docker compose up --build -d web
docker compose exec web cat /data/bootstrap.token
```

Open **http://127.0.0.1:8000**, enter the bootstrap token, and finish setup. Then start the worker:

```sh
docker compose up --build -d worker
```

The web port is bound to localhost. Keep the data volume and encryption key backed up;
`docker compose down -v` deletes the volume. See the
[deployment guide](https://github.com/simtiaz019/NotiDeck/blob/main/docs/deployment.md)
for PostgreSQL, HTTPS, supervision, and backups.

## A console for everyday operations

View recent events, find failed deliveries, manage channels and routing rules, and
inspect the queue without writing SQL.

![NotiDeck web console showing notification totals, recent events, and severity breakdown.](https://raw.githubusercontent.com/simtiaz019/NotiDeck/main/docs/console-tested.png)

*Console screenshot uses synthetic demonstration data.*

## Learn more

| I want to… | Guide |
| --- | --- |
| Install or configure NotiDeck | [Installation](https://github.com/simtiaz019/NotiDeck/blob/main/docs/installation.md) · [Configuration](https://github.com/simtiaz019/NotiDeck/blob/main/docs/configuration.md) |
| Integrate an application | [API](https://github.com/simtiaz019/NotiDeck/blob/main/docs/api.md) · [Routing](https://github.com/simtiaz019/NotiDeck/blob/main/docs/routing.md) |
| Customize messages | [Notification templates](https://github.com/simtiaz019/NotiDeck/blob/main/docs/notification-templates.md) |
| Deploy safely | [Deployment](https://github.com/simtiaz019/NotiDeck/blob/main/docs/deployment.md) · [Security](https://github.com/simtiaz019/NotiDeck/blob/main/docs/security.md) |
| Understand current scope | [Support boundaries](https://github.com/simtiaz019/NotiDeck/blob/main/docs/limitations.md) · [Changelog](https://github.com/simtiaz019/NotiDeck/blob/main/CHANGELOG.md) |
| Contribute or build a provider | [Development](https://github.com/simtiaz019/NotiDeck/blob/main/docs/development.md) · [Provider plugins](https://github.com/simtiaz019/NotiDeck/blob/main/docs/plugins.md) |

NotiDeck is licensed under [Apache-2.0](https://github.com/simtiaz019/NotiDeck/blob/main/LICENSE).
