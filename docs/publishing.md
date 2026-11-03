# Publishing agentdata

The package is built from `pyproject.toml` using setuptools. It has no runtime
dependencies and supports Python 3.10+. Release work is reviewed on a branch,
merged into `main`, and then tagged. Pushing a tag publishes to PyPI after all
package checks pass.

## One-time account setup

In the GitHub repository settings, create an environment named `pypi`. Under
deployment branches and tags, select **Selected branches and tags** and add a
**tag** rule for `v*`. A branch-only rule for `main` will block tag deployments.

In your PyPI account's [Publishing settings](https://pypi.org/manage/account/publishing/),
add a pending GitHub publisher for the first release:

| Field | Value |
|---|---|
| PyPI project name | `agentdata` |
| GitHub owner | `dicaria` |
| Repository | `agentdata` |
| Workflow filename | `release.yml` |
| Environment | `pypi` |

If the PyPI project already exists and you maintain it, add the same publisher
under that project's Publishing settings instead. A pending publisher creates
the project on first successful publication; it does not reserve the package
name. See [PyPI's setup guide](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).
No PyPI API token or repository secret is needed.

This repository is a release mirror of the development line (see
[`CONTRIBUTING.md`](../CONTRIBUTING.md)). Preserve the workflow, release checks,
and packaging metadata when syncing the mirror; include these changes in the
development line so a later sync does not overwrite them.

## Check a release locally

Use Python 3.11+ for the release check script, which uses `tomllib` from the
standard library. The installed SDK still supports Python 3.10.

```bash
python -m venv .venv
```

Activate it with `source .venv/bin/activate` on macOS/Linux or
`.venv\Scripts\Activate.ps1` in Windows PowerShell, then run:

```bash
python -m pip install build twine
python scripts/check_release.py --tag v0.3.26
python -m build
python -m twine check --strict dist/agentdata-0.3.26.tar.gz dist/agentdata-0.3.26-py3-none-any.whl
python -m pip install --no-deps --force-reinstall dist/agentdata-0.3.26-py3-none-any.whl
python -I scripts/smoke_test.py
```

Use a clean `dist/` directory when preparing a release so old versions are not
mistaken for current artifacts. The smoke check imports the installed wheel,
checks module coverage, exercises all nine CLI entry points, and validates
README API signatures and CLI syntax without querying upstream services.

## Release

1. Update the bare `version` value in `pyproject.toml` and `__version__` in
   `agentdata/__init__.py` together. Update the pinned install examples in
   `README.md` to the same version.
2. Open a pull request into `main`. The `release` workflow builds an sdist and
   a wheel **from that sdist**, checks metadata and README rendering, and tests
   the wheel on Python 3.10–3.13 on Linux and Python 3.13 on Windows/macOS.
3. Merge after checks pass, then tag the merged commit. For this release:

   ```bash
   git switch main
   git pull --ff-only origin main
   git tag -a v0.3.26 -m "Release 0.3.26"
   git push origin v0.3.26
   ```

4. The tag run checks that `v0.3.26` matches both source versions and that the
   tagged commit belongs to `main`. Only the publish job receives the OIDC
   permission; it downloads the checked distributions and uploads them without
   checking out or building repository code. This follows the
   [PyPA publishing workflow](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/).
5. Confirm the workflow succeeded and install the published version in a fresh
   environment with `python -m pip install --no-cache-dir agentdata==0.3.26`.

If publication fails, correct the account/environment setup and rerun the failed
job. PyPI does not let you replace uploaded distribution files: if an uploaded
release needs a code or metadata change, increment the version and release a
new tag. Do not enable `skip-existing` to hide an incomplete upload.
