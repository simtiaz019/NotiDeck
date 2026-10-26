# Contributing

Read README.md and docs/development.md. Use Python 3.11+ and Node 22.12+. Keep provider
transport, API handlers, routing and persistence separate. Include regression tests
for security and queue transitions. Never include live credentials or customer payloads
in fixtures. Run `make check test build` before proposing a change. Add an Alembic
revision for schema changes; never rewrite a released migration. Describe test coverage
and unverified environments explicitly. Contributions are licensed under Apache-2.0.
