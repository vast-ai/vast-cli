# Deploying a CLI release

Tell your agent **"prepare a release"**. It picks the version, checks with you, and ships it. Questions? Reach out to Sammy or #cli-help on Slack.

## Agent instructions

1. On an up-to-date `master`, run `git log $(git describe --tags --abbrev=0)..master --oneline`. Any `feat` → bump minor (`1.8.3` → `1.9.0`); otherwise bump patch (`1.8.3` → `1.8.4`).
2. Tell the user the version and wait for their go-ahead. The tag publishes to PyPI and the installer immediately, with no undo.
3. `git tag vX.Y.Z && git push origin vX.Y.Z`
4. Watch it with `gh run watch --repo vast-ai/vast-cli` and report back. If PyPI looks stale, it's CDN cache. Add `?nocache=$RANDOM` to the URL.

A bad release is fixed by releasing a newer one. Users can roll back with `vastai update --version X.Y.Z`.
