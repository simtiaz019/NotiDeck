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
- [x] Set public repository/documentation/issue URLs for simtiaz019/NotiDeck in pyproject.toml.
- [ ] Configure and document a private security reporting contact; no contact address was supplied.
- [ ] Configure GitHub environments `testpypi` and `pypi` with required reviewers and trusted publishers for this repository and `release.yml`.
- [ ] Review wheel/sdist contents, versions, checksums and dependency audits.
- [ ] Publish the candidate to TestPyPI using the manual workflow; install/test it in isolation.
- [ ] After acceptance, promote version to `0.1.0` in pyproject.toml, Python, frontend package/lock/UI, changelog and installation docs. Rebuild; never rename an RC archive.
- [ ] Rerun CI and clean-wheel smoke for the final artifacts. Push the matching `v0.1.0` tag to trigger the release workflow automatically.

The release workflow now waits for the reusable full CI workflow (platform checks, database
services, browser and Docker delivery smoke), then builds distributions and runs a clean-wheel
smoke. Tag pushes (`v*`) publish to PyPI automatically after those checks pass. Manual dispatch
remains available for TestPyPI and tagged PyPI releases. Production publishing requires a
matching version tag. Publishing uses OIDC,
not a long-lived API token. Repository environment approvals and publisher ownership must
be configured by the maintainer; a workflow file cannot configure those account settings.

Upload only artifacts for the intended version. `dist/` may contain the preserved original
0.1.0 local alpha artifacts; do not upload `dist/*` from this development directory. The
workflow builds in a clean checkout. Old local alpha `0.1.0` archives must be replaced by
freshly rebuilt final artifacts after candidate acceptance.


## Publish like IsoZap: Git tag → GitHub Actions → PyPI

This follows IsoZap's `.github/workflows/release.yml`: tag-triggered build, artifact transfer,
then OIDC Trusted Publishing using the `pypi` environment. NotiDeck also requires its full CI
workflow to succeed before publishing. No API-token secret is needed.

1. In the NotiDeck GitHub repository, open Settings → Environments and create `pypi`.
   Configure required reviewers if you want an approval before upload.
2. Sign into PyPI and open https://pypi.org/manage/account/publishing/ . For a new project,
   add a pending GitHub publisher using these exact values:

   | Field | Value |
   | --- | --- |
   | PyPI project name | `notideck` |
   | Owner | `simtiaz019` |
   | Repository name | `NotiDeck` |
   | Workflow filename | `release.yml` |
   | Environment name | `pypi` |

   If you already own the PyPI project, add the publisher under that project's Publishing
   settings instead. IsoZap's publisher does not authorize NotiDeck; register this one separately.
3. Commit and push the workflow/metadata/documentation updates, then wait for green CI:

   ```sh
   git add .github/workflows/ci.yml .github/workflows/release.yml pyproject.toml docs/release.md
   git commit -m "Publish NotiDeck tags through PyPI Trusted Publishing"
   git push origin main
   ```

4. The current version is `0.1.0rc1`. To publish that candidate, after CI and acceptance pass:

   ```sh
   git tag -a v0.1.0rc1 -m "NotiDeck 0.1.0rc1"
   git push origin v0.1.0rc1
   ```

   Pushing the tag starts publication. It does not require creating a GitHub Release.
   For stable `0.1.0`, first promote versions, rebuild/test, commit and push those changes,
   then use `v0.1.0` instead. Never tag the RC commit as `v0.1.0`.
5. Watch https://github.com/simtiaz019/NotiDeck/actions/workflows/release.yml and approve
   the environment deployment if configured. Verify the PyPI page and clean installation:

   ```sh
   python -m pip install "notideck==0.1.0rc1"
   notideck --version
   ```

For TestPyPI, register the same owner/repository/workflow on TestPyPI with environment
`testpypi`, create that GitHub environment, then use Actions → Release → Run workflow →
target `testpypi`. Only manual dispatch targets TestPyPI; a `v*` tag push targets PyPI.

Reference: https://github.com/simtiaz019/IsoZap/blob/main/.github/workflows/release.yml
and https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/ .
