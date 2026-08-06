# Architecture

The CLI has four boundaries:

1. `composer.py` invokes Composer as an argument list, parses its JSON output, reads root requirements, and builds execution commands.
2. `releases.py` uses Packagist for release timestamps and the source forge APIs for changelog data.
3. `versions.py` performs only display-level semantic-version classification. Composer remains the source of truth for constraint resolution.
4. `cli.py` coordinates filtering, confirmation, and command execution; `tui.py` provides the Textual keyboard interface, its modal screens, and the generated Composer plan view.

Network and process access are injectable (`JsonClient` transport and `ComposerClient` runner), so tests do not contact external systems. Any failed optional release lookup emits a warning and leaves Composer's update discovery usable.

The Textual table owns keyboard navigation. Its secondary changelog, version, plan, dry-run result, and confirmation screens intercept their own controls: `q` closes the current secondary screen, while `i` and `v` replace a secondary screen rather than stacking them. `--major` is applied when populating selectable version rows, not only when rendering the main table. The table owns dry runs (`d`) and the `--with-all-dependencies` toggle (`w`); the latter is shown in the plan, confirmation, and dry-run result, and is preserved when returning to the table after a dry run. Composer discovery defaults to direct dependencies; `--no-direct` expands it to transitive dependencies.

## Release process

Create a GitHub repository, configure PyPI Trusted Publishing for the `pypi-publish.yml` workflow, and push a signed `vX.Y.Z` tag. The workflow builds the package and publishes it. Verify the availability of `composer-upgrade` on PyPI immediately before the first release.
