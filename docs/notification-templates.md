# Database notification templates

Five reusable templates supplement Default notification:

| Template | Suggested routing category | Typical level | Metadata fields |
| --- | --- | --- | --- |
| PostgreSQL audit alert | postgres-audit | WARNING / ERROR | node, type, event_time, database, user, client, command, db_severity, sqlstate, audit_command |
| PostgreSQL replication lag | replication | WARNING / CRITICAL | node, primary, replica, database, lag_seconds, threshold_seconds, replay_state, event_time |
| Database connection failure | database-connection | ERROR / CRITICAL | node, database, host, port, user, client, error_code, attempts, event_time |
| PostgreSQL long-running query | slow-query | WARNING | node, database, user, pid, duration_seconds, threshold_seconds, state, wait_event, event_time |
| Database backup status | backup | INFO / ERROR | node, database, job, status, backup_type, started_at, finished_at, duration_seconds, size_bytes, destination |

All include the source, notification severity, creation time, event details and message.
Missing optional metadata renders blank instead of failing. `metadata.monitor` optionally
identifies the originating monitor while `source` remains the authenticated NotiDeck source.
`metadata.event_created_at` optionally preserves the monitor's timestamp; otherwise the
actual ingestion timestamp is used. `metadata.icon` overrides the template's fixed default
icon, useful when reusing a template for different severity levels. The Level text always
reflects the event's severity. Metadata values do not determine routing severity automatically.

The audit template deliberately keeps notification `severity` separate from
`metadata.db_severity`: the supplied example is a WARNING notification about an ERROR log.
The complete sample payload is in `examples/postgres_audit_event.json`.

## Use in Console

1. Open Templates to review or edit the templates.
2. Edit the intended routing rule and select a **Notification template** by name.
3. Set the desired source/environment/category/severity conditions and destinations, then save.
4. Submit an event whose metadata uses the fields above.

A WARNING event does not match a rule with severity gte ERROR. Use a WARNING-capable
rule for the supplied audit example. Adding a template does not change existing routes or
send any notifications. Already queued jobs retain their previously rendered messages.

Each template has plain-text and HTML-email variants. HTML variable values are escaped.
Text does not contain Markdown markup or artificial hyperlinks, so it is readable in
plain-text Telegram and email channels. The generic provider adds its standard severity
prefix to the title. Rich Telegram bold formatting is not enabled by these templates.

Fresh setups include the library. For an existing installation, after installing the updated
package run `python examples/install_database_templates.py` from the repository with the
same NOTIDECK_CONFIG_DIR as the server. This adds only missing template names, audits each
creation, preserves edited templates and never changes rules. The current local installation
has already been updated with these five templates.

To send the sample after configuring its route (submits a real notification):

```sh
curl --fail-with-body http://127.0.0.1:8000/api/v1/notifications \
  -H "Authorization: Bearer $NOTIDECK_API_KEY" \
  -H 'Content-Type: application/json' \
  --data-binary @examples/postgres_audit_event.json
```

Use your source's key and adjust the sample's source name if needed. Avoid sending passwords,
connection strings, or sensitive SQL bind values in metadata or notification messages.
