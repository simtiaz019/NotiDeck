# Release gates

**0.1.0rc1** is prepared for final user testing. No publication has been performed.
See [validation evidence](validation.md), [upgrade steps](upgrade-0.1.0rc1.md) and
[scope limitations](limitations.md). The original user CSV is preserved.

## Before publishing

- [ ] Complete candidate acceptance, especially existing-installation upgrade, email and Telegram regression, queue recovery and restore.
- [ ] Run the GitHub CI matrix from the actual hosted repository. Local macOS/Linux-container checks do not establish Windows or every Python-version support.
- [ ] Review support claims: SQLite/PostgreSQL/MySQL core; Oracle experimental; unverified credentialed adapters must stay identified as such.
- [ ] Review production security, reverse proxy HTTPS and deployment-specific TLS/egress settings.
- [ ] Confirm PyPI/TestPyPI ownership of `notideck`.
- [ ] Set actual repository/documentation/issue URLs in pyproject.toml. No repository identity was supplied.
- [ ] Configure and document a private security reporting contact; no contact address was supplied.
- [ ] Configure GitHub environments `testpypi` and `pypi` with required reviewers and trusted publishers for this repository and `release.yml`.
- [ ] Review wheel/sdist contents, versions, checksums and dependency audits.
- [ ] Publish the candidate to TestPyPI using the manual workflow; install/test it in isolation.
- [ ] After acceptance, promote version to `0.1.0` in pyproject.toml, Python, frontend package/lock/UI, changelog and installation docs. Rebuild; never rename an RC archive.
- [ ] Rerun CI and clean-wheel smoke for the final artifacts. Create matching `v0.1.0` tag and invoke the release workflow with target `pypi`.

The release workflow now waits for the reusable full CI workflow (platform checks, database
services, browser and Docker delivery smoke), then builds distributions and runs a clean-wheel
smoke. Production publishing also requires a matching version tag. Publishing uses OIDC,
not a long-lived API token. Repository environment approvals and publisher ownership must
be configured by the maintainer; a workflow file cannot configure those account settings.

Upload only artifacts for the intended version. `dist/` may contain the preserved original
0.1.0 local alpha artifacts; do not upload `dist/*` from this development directory. The
workflow builds in a clean checkout. Old local alpha `0.1.0` archives must be replaced by
freshly rebuilt final artifacts after candidate acceptance.
