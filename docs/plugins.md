# Provider plugin API (v1, alpha)

Install trusted Python packages on the server/worker environment. Register an entry point
under `notideck.providers`. Plugins load once when creating the app/worker registry; they
cannot be uploaded or executed as arbitrary code by web requests. Duplicate names are
rejected. Restart both processes after installing/updating plugins.

The Provider protocol is in `notideck.providers`. Implement provider_type,
configuration_schema, validate_configuration, supported_capabilities, test_connection
and send. Return `Result(success, retryable, message_id, code, error, retry_after,
accepted_at)`. Diagnostics must be safe and redacted. `accepted_at` is a UTC epoch value.
Timeouts must be bounded well below the 180-second lease. Do not fabricate acceptance.
Use NotiDeck's `safe_http` helper for HTTP to retain SSRF and TLS protections.

Schemas expose properties with type and secret flags; validation remains the provider's
responsibility. The Console currently renders string fields and a few known structured
fields, so more complex plugin configuration may require the API. All configuration is
encrypted by the core. A separate classify_error method is not required in this protocol;
classification belongs in the structured result returned by send.

See `examples/provider_plugin` for an installable webhook relay provider. It delegates
transport to the core generic-webhook adapter rather than inventing a fake provider.
Version 0.1 is an alpha API: pin a compatible NotiDeck minor series and test integrations
before upgrading. A formal backwards-compatibility guarantee starts only after a stable
protocol release.
