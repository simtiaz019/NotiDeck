# Security model

Passwords use Argon2id. Minimum password length is 12 (configurable upward), maximum 256,
with at least one letter and one nonletter. Administrator password reset changes the hash
and revokes all target sessions. Self password changes require the current password and
also revoke all sessions. There is no email-based reset flow or default administrator.

Roles are explicit backend capabilities: ADMIN has all operations, OPERATOR reads events
and configures channels/rules/recipients/templates plus pause/resume/retry, VIEWER reads
operational data. Only ADMIN manages sources/keys/users/settings/audits, retention and
queue cancellation. These are workspace-wide roles, not per-source or per-channel grants.
Users cannot disable/demote their own administrator account. Disabling a user immediately
invalidates authentication and edits revoke their sessions.

Session tokens and API keys are cryptographically random and stored hashed. Sessions
expire after eight hours. Cookie-authenticated mutations require a session-bound CSRF
header, and cross-origin requests are rejected. CORS is not enabled. Secure cookies are
automatic on direct HTTPS; use NOTIDECK_SECURE_COOKIES=1 behind TLS termination. The
readable CSRF token is not an authentication credential on its own.

Bootstrap requires a private local random token. Setup endpoints refuse initialized
installations. The setup token file and encryption key are mode 0600 on POSIX in a
0700-created directory; Windows users must additionally restrict directory ACLs. Generated
secrets are never printed in logs. API keys and webhook secrets are returned once through
an authorized operation, as required to configure callers.

Credentials and the saved database URL are encrypted using Fernet, with the master key
supplied through an environment secret or a private local file. Notification content is
stored as application data, **not field-encrypted**; protect database storage/backups and
use database TLS. UI display escapes event data. Provider diagnostics persist safe status
codes and redacted messages, never raw response bodies or authentication headers.

Back up the master key securely. Losing it makes channel/database credentials unrecoverable.
Changing the key alone does not rotate ciphertext. An automated re-encryption/rotation tool
is not implemented; migrate secrets in a controlled maintenance procedure before replacing
keys. Do not store the key in the application database or commit it to source control.

HTTP SSRF protections validate DNS at connection time and pin the connected address,
reject redirects and URL userinfo, reject unsafe Host/length/transfer headers, and block
nonpublic destinations unless a deployment-owned CIDR allowlist permits them. This applies
to all built-in HTTP transports. SMTP configuration is administrator-trusted and not
covered by the HTTP validator. No arbitrary shell execution is exposed by APIs. Locally
installed provider plugins are executable trusted code and must be reviewed separately.

Structured request logs contain generated correlation ID, method, status and duration,
not payloads, keys, query strings or provider URLs. Worker logs contain delivery ID,
status and duration. Significant mutations are audited without credential values. Audits
are application records, not cryptographically tamper-evident storage. Backups and external
log retention policies remain deployment responsibilities.

Known gaps: independent security review, MFA/SSO, granular resource permissions, external
metrics scrape credentials, key rotation tooling, session cleanup scheduling and robust
proxy-specific deployment tests. Do not represent this alpha as independently audited.
