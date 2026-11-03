# Release process

NotiDeck publishes from a version tag through GitHub Actions and PyPI Trusted Publishing.
The release workflow runs the complete CI matrix, builds distributions from a clean
checkout, validates them with Twine and a clean-wheel smoke test, and only then uploads.
Long-lived PyPI API tokens are not used.

## One-time repository setup

1. In GitHub, create environments named `pypi` and `testpypi`. Add required reviewers if
   releases should pause for manual approval.
2. In PyPI, configure a trusted publisher for the project with these values:

   | Field | Value |
   | --- | --- |
   | Project | `notideck` |
   | Owner | `simtiaz019` |
   | Repository | `NotiDeck` |
   | Workflow | `release.yml` |
   | Environment | `pypi` |

3. Configure the equivalent publisher on TestPyPI with environment `testpypi` if candidate
   uploads are required.
4. Enable GitHub private vulnerability reporting and ensure maintainers receive security
   notifications.

## Stable release checklist

- [ ] Choose a PEP 440 version that does not already exist on PyPI.
- [ ] Update the version in `pyproject.toml`, `src/notideck/__init__.py`, frontend package
      metadata, visible console text, and `CHANGELOG.md`.
- [ ] Remove prerelease wording and `--pre` installation commands for a stable release.
- [ ] Run the backend, frontend, wheel, browser, database, and Docker checks.
- [ ] Review the wheel and sdist contents; confirm no credentials or local data are included.
- [ ] Commit and push the release changes to `main`; require a green CI run.
- [ ] Create an annotated tag that exactly equals `v` plus `notideck.__version__` and push it.
- [ ] Confirm the Release workflow succeeds and the new version appears on PyPI.
- [ ] Install the exact PyPI version in a clean Python 3.11+ environment and run
      `notideck --version` plus a first-run smoke test.

The production workflow rejects a tag that does not match the package version. Never
rename a release-candidate archive or reuse a version already uploaded to PyPI; package
files are immutable.

## Publish 0.1.0

After the final release commit is green on `main`:

```sh
git tag -a v0.1.0 -m "NotiDeck 0.1.0"
git push origin v0.1.0
```

The tag triggers `.github/workflows/release.yml`. Follow its progress at
<https://github.com/simtiaz019/NotiDeck/actions/workflows/release.yml>. If the `pypi`
environment requires approval, an authorized reviewer must approve the deployment.

After success, verify the public artifact rather than a local wheel:

```sh
python -m venv .release-smoke
source .release-smoke/bin/activate
python -m pip install --upgrade pip
python -m pip install "notideck==0.1.0"
notideck --version
python -m pip uninstall -y notideck
deactivate
```

Windows PowerShell uses `.\.release-smoke\Scripts\Activate.ps1` for activation.

## TestPyPI

Use Actions → Release → Run workflow and select `testpypi`. TestPyPI often cannot resolve
all production dependencies, so install the artifact while obtaining dependencies from
PyPI when necessary. A TestPyPI upload is a separate immutable release and is not promoted
by copying files to production.

## Recovery

If validation or publication fails, fix the cause on `main`, increment the version, and
publish a new tag. Do not delete and recreate a public version. If a release has a severe
problem, yank it in PyPI, document the reason, and ship a corrected version.
