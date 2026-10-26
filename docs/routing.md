# Routing, templates and delivery semantics

Rules are read for each ingested event; edits need no server restart. Order is ascending
priority then UUID for deterministic ties. Conditions are ANDed. Empty conditions match
all events. All matching rules contribute destinations unless a matching rule sets stop.
Overlapping rules deduplicate `(channel_id, resolved recipient address)`; the first match
wins for the selected template and delivery priority. Explicit duplicate fan-out is not
supported in this alpha.

Fields include source (name), source_id, environment, severity, category, tags and dotted
metadata paths. Operators: equals, not_equals, in, not_in, contains, exists, greater, less,
gte and lte. Severity comparison orders DEBUG < INFO < WARNING < ERROR < CRITICAL.
Other ordered comparisons require numbers. Missing properties fail ordered comparisons.
No eval or executable rule code exists.

Production example: environment equals production AND severity equals CRITICAL, with
Telegram, Slack and email targets. Staging example: environment equals staging AND
severity gte ERROR, with a staging Slack target. An INFO event without a matching rule
is stored as UNROUTED, with no delivery jobs.

Each target has channel_id and optionally recipient_id or group_id. Recipients store
provider-name-to-address mappings. Groups store recipient IDs. Addresses missing for the
selected provider are skipped. Without either recipient/group, the channel's configured
default destination is used. For generic webhooks, the URL belongs to the channel; a
recipient override does not change its destination URL. Use distinct webhook channels.

Templates provide title, text and optional email HTML. Only variable interpolation and
escape/default/upper/lower filters are allowed. Calls, arithmetic, loops, imports and
object introspection are rejected. HTML variables autoescape, and the Console renders
previews as text. Templates are rendered once during ingestion and stored on the job,
so later template edits do not change pending messages. Channel credentials are read at
send time, allowing key rotation without recreating pending events.

`POST /routes/simulate` shows matches without persisting jobs or contacting providers.
`POST /templates/preview` renders sample data. Ingested template variables include id,
title, message, severity, environment, source, created_at and metadata.

## Durable queue

Ingestion persists the event and all jobs in one transaction. Workers claim eligible
jobs using a conditional status transition. PostgreSQL/MySQL also use SKIP LOCKED.
SQLite and Oracle use the portable conditional-claim fallback. A claim stores a random
lease token; only its owner may finalize the attempt. Lease duration is 180 seconds;
expired claims become retry scheduled on polling. Built-in provider requests have bounded
timeouts; custom plugins must also respect this lease window. A lease-renewal protocol
for long-running external plugins is not implemented.

Per-channel spacing reserves the next dispatch time atomically, including across workers.
Retry delay grows exponentially with jitter and is bounded at roughly one hour before
Retry-After is considered; provider Retry-After can extend it. Exhausted transient errors
become DEAD_LETTER; permanent failures become FAILED. Manual retry starts a fresh retry
budget and preserves attempt history. Graceful worker shutdown stops accepting new work
and waits for current calls. Restarted workers recover expired claims.

Delivery is at least once. A crash after provider acceptance but before database commit
can cause a duplicate. Provider idempotency is not universally available and is not
claimed here. SENT means accepted by the provider/SMTP relay. Receipt-confirmed delivery
states are reserved for future work. Aggregate notification status is PENDING while any
job is live, SENT if all accepted, PARTIAL for mixed terminal outcomes with acceptance,
FAILED for unsuccessful terminal outcomes, CANCELLED if all cancelled, or UNROUTED.
