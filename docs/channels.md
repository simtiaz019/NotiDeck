# Providers and channels

Create multiple named channels per provider. All configuration is encrypted at rest;
known secrets are masked when editing, and list responses contain no configuration.
Channel tests make real sends, may incur charges, and are limited to five per minute.
Disabled channels receive no new jobs and are not dispatched. Paused channels can queue
new jobs but do not dispatch them. Deletion is refused for channels referenced by rules
or delivery history; disable those channels instead. Duplication copies credentials
server-side and starts the new channel disabled.

| Provider ID | Required configuration | Notes |
| --- | --- | --- |
| telegram | bot_token, chat_id | Official Bot API sendMessage; optional parse_mode |
| email | host, port, from_address, to | tls=starttls (default), tls, or none; optional username/password/cc/bcc |
| slack | webhook_url OR bot_token + channel | Incoming webhooks or chat.postMessage; severity color attachment |
| discord | webhook_url | Embed with severity color; automatic mentions disabled |
| webhook | url | method POST/PUT/PATCH, headers, bearer_token or basic_username/basic_password, hmac_secret, payload |
| whatsapp | access_token, phone_number_id, recipient, api_version, template_name, language | Official Meta Cloud API approved-template send; optional components |
| sms | account_sid, auth_token, from_number, to | Twilio Messages API; use E.164 international numbers |
| signal | url, account, recipient | Separately installed signal-cli-rest-api bridge, POST /v2/send |

All support `timeout` in seconds (1–30, default 15). Email to/cc/bcc use conventional
comma-separated address lists. SMTP is an administrator-trusted integration; its host
is not governed by the HTTP CIDR policy. Use network egress controls to restrict it.
SMTP credentials should only be sent over TLS; `tls=none` is for explicitly trusted local relays.

For HTTP webhook JSON payloads, string values support safe `{{ notification.title }}`
interpolation, recursively through objects and arrays. Omitting payload sends the rendered
notification object. WhatsApp components can use the same interpolation, for example:

```json
[{"type":"body","parameters":[{"type":"text","text":"{{ notification.title }}"}]}]
```

The template must already be approved for the configured WhatsApp language/category.
Business onboarding, user consent, conversation policy and provider limits remain the
operator's responsibility. No API version is hard-coded: configure a version supported
by your Meta app. WhatsApp receipt callbacks are **not implemented**. `SENT` means
provider acceptance, never a claimed recipient delivery/read receipt.

Signal has no official general-purpose bot API. The optional bridge requires its own
Signal account registration/linking, secure hosting and lifecycle management. NotiDeck
does not install or supervise it. If hosted on a private address, add only its network
to `NOTIDECK_OUTBOUND_ALLOW_NETWORKS` and secure the bridge independently.

HTTP requests do not follow redirects or inherit proxy environment variables. DNS
addresses are validated at socket connection time and the selected validated address
is pinned while preserving the original hostname for TLS. All resolved addresses must
be public or explicitly allowed. Loopback, private, link-local and metadata destinations
are blocked by default. Any allowlist exception must be set by the deployment operator,
not by an API caller. The implementation uses HTTPX/httpcore transport internals, so
those dependencies are constrained and changes require the SSRF regression suite.

HTTP 408/425/429 and 5xx responses are retryable. Telegram retry_after and HTTP Retry-After
are honored; timeouts and network failures retry. Provider response bodies are never
persisted. Malformed configuration and most other 4xx failures are terminal. Response
bodies are capped at 64 KiB. Destination-specific message size and provider content rules
may reject payloads; NotiDeck does not silently truncate messages.

References checked during implementation:
[Telegram Bot API](https://core.telegram.org/bots/api),
[Twilio Messages](https://www.twilio.com/docs/messaging/api/message-resource),
[Slack chat.postMessage](https://docs.slack.dev/reference/methods/chat.postMessage/),
[Discord webhooks](https://discord.com/developers/docs/resources/webhook),
[Meta WhatsApp Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api/),
[signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api).
