# HTTP API

The versioned API is under `/api/v1`. `/api/openapi.json` is the authoritative,
generated schema. `/api/docs` provides a locally bundled Swagger UI that works without
external CDN access and respects the application's content security policy.

## Authentication

Console login: `POST /auth/login` with `username` and `password`. The response sets an
8-hour HttpOnly SameSite=Strict session cookie and a readable CSRF cookie. Send the CSRF
value in `X-CSRF-Token` on all cookie-authenticated mutations, including logout. Login
has per-IP and per-username database-backed limits. Origins and Fetch Metadata are checked.
Sessions and API keys are stored as SHA-256 hashes of high-entropy random tokens.

Machine ingestion: `Authorization: Bearer nd_...`. Create source-scoped keys with
`POST /sources/{id}/keys`; scopes currently support `notifications:write`. Optional
`expires_at` is a future Unix timestamp. A key is displayed once. Rotate by creating a
replacement, migrating the caller, then `POST /keys/{id}/revoke`. Disabling a source
immediately prevents ingestion. Network restrictions use the actual ASGI peer address;
forwarded headers are not trusted by the default CLI server.

## Ingestion

```json
{
  "source": "production-database",
  "environment": "production",
  "severity": "CRITICAL",
  "title": "Production Database Replication Lag",
  "message": "Lag exceeded the configured threshold.",
  "category": "database",
  "tags": ["postgresql", "replication"],
  "metadata": {"hostname": "db-primary", "lag_seconds": 120},
  "idempotency_key": "replication-alert-123"
}
```

`POST /notifications` returns 202 with `id`, aggregate `status`, and `replayed`.
The key's source is authoritative; optional `source` must match its ID or name.
An idempotency key is unique within a source. Repeating the same normalized payload
returns the original event and creates no jobs. Reusing a key with a different payload
returns 409. Omitting a key requests a new event. Keys remain reserved until notification
retention deletes the associated event; audit retention is separate.

Signed inbound webhook: first rotate/generate a source webhook secret through
`POST /sources/{id}/webhook-secret`, then `POST /webhooks/{id}` with
`X-NotiDeck-Timestamp` (Unix seconds) and `X-NotiDeck-Signature` (hex HMAC-SHA256 over
`timestamp + "." + exact request bytes`). Timestamps must be within five minutes.
An idempotency key is mandatory. This is NotiDeck's inbound format, not Meta's receipt format.

Requests are limited to 256 KiB; titles to 500 characters and messages to 50,000.
Responses use `{"error":{"message":"..."}}`; validation includes safe field locations
without echoing input values. Request IDs are returned in `X-Request-ID`. Source rate
limits are atomic fixed-window limits per minute, so boundary bursts are possible.

## Administration

- `/channels`, `/channels/{id}`, `/channels/{id}/test`, `/channels/{id}/duplicate`
- `/routes`, `/routes/{id}`, `/routes/simulate`
- `/sources`, `/sources/{id}`, `/sources/{id}/keys`, `/keys/{id}/revoke`
- `/resources/recipients`, `/resources/groups`, `/resources/templates` (GET/POST/PATCH)
- `/templates/preview`, `/users`, `/users/{id}`, `/auth/password`
- `/notifications`, `/notifications/{id}`, `/notifications/{id}/deliveries`
- `/dashboard`, `/audits`, `/settings`, `/retention`
- `/health/live`, `/health/ready`, `/system/version`, `/metrics`

List endpoints use `offset` and `limit` (1–100). Notification filters: severity,
environment, source_id, status, title search. Audit filters: operation. Queue filters:
status, channel_id, environment, source_id, severity and before (UTC epoch).

Queue `/queue/stats` reports actual persisted counts, current minute attempt count,
channel backlogs, oldest age, and worker heartbeats. `/queue/pause` and `/queue/resume`
accept optional channel_id. `/queue/retry`, `/queue/cancel`, `/queue/clear` accept ids,
channel_id, environment, source_id, severity, before, reason and confirm. With confirm
false, they preview a count. With confirm true, they update eligible states atomically.
Cancellation requires ADMIN and only affects PENDING/RETRY_SCHEDULED. Retry accepts
FAILED/DEAD_LETTER and requires OPERATOR or ADMIN. An in-progress send cannot be recalled.
The count is recalculated when confirmed; it is not a frozen snapshot of the preview.

`/metrics` emits Prometheus text for delivery-state gauges, persisted error count and
mean attempt latency. It currently uses administrator session authentication; a dedicated
scrape-token mechanism is not implemented. Retention deletes at most 500 expired terminal
notifications per explicit invocation and preserves audits.
