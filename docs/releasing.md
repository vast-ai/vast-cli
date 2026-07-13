# Releasing

A release is a tag push; CI does everything else (`python-publish.yml`).

```bash
git checkout master && git pull --ff-only
git log $(git describe --tags --abbrev=0)..master --oneline   # what's shipping
git tag vX.Y.Z && git push origin vX.Y.Z
```

- Version: bump minor for feats, patch for fixes. No leading zeros; CI only
  fires on `vX.Y.Z`.
- Tag only a green master head (check the PR checks of the commits shipping).
- Pushing the tag is the release — it publishes to PyPI immediately and the
  GitHub Release assets are the live installer deploy (`releases/latest` is
  what vast.ai redirects serve). There is no undo; a bad release is fixed by
  releasing a newer version.

## Verify (CI does this too, but confirm before walking away)

```bash
gh run watch --repo vast-ai/vast-cli   # all 3 jobs green
curl -fsSL https://github.com/vast-ai/vast-cli/releases/latest/download/manifest.env | grep LATEST
curl -fsSL https://pypi.org/pypi/vastai/json | python3 -c "import json,sys; print(json.load(sys.stdin)['info']['version'])"
```

Rollback for users: `vastai update --version X.Y.Z` (pins/downgrades).
Break-glass manual release: docs/install-design.md §13.
