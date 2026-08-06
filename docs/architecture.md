# Architecture

The CLI has four boundaries:

1. `composer.py` invokes Composer as an argument list, parses its JSON output, reads root requirements, and builds execution commands.
2. `releases.py` uses Packagist for release timestamps and the source forge APIs for changelog data.
3. `versions.py` performs only display-level semantic-version classification. Composer remains the source of truth for constraint resolution.
4. `cli.py` coordinates filtering, the Rich terminal interface, confirmation, and command execution.

Network and process access are injectable (`JsonClient` transport and `ComposerClient` runner), so tests do not contact external systems. Any failed optional release lookup emits a warning and leaves Composer's update discovery usable.

## Release process

Create a GitHub repository, configure PyPI Trusted Publishing for the `pypi-publish.yml` workflow, and push a signed `vX.Y.Z` tag. The workflow builds the package and publishes it. Verify the availability of `composer-upgrade` on PyPI immediately before the first release.
