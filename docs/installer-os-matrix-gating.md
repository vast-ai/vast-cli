# TODO: flip the installer OS-matrix CI from canary → gating

The `os-matrix` job in `.github/workflows/installer-ci.yml` (added in #427) runs
the real `install.sh` across `alpine:latest`, `debian:stable-slim`,
`ubuntu:20.04`, and `macos-latest`. It currently ships as a **non-blocking
canary** — `continue-on-error: true` — so a flaky leg can't block merges while
the matrix proves itself.

## The change

Once it has been green across a few runs, **delete the `continue-on-error: true`
line** from the `os-matrix` job so the matrix gates PRs:

```yaml
  os-matrix:
    needs: build-wheel
    continue-on-error: true   # <-- remove this line to make the matrix blocking
```

## Preconditions before flipping

- [ ] #427 merged to `master` (the `os-matrix` job only exists there afterward).
- [ ] Matrix green across a few real PR runs (first run on #427 was green on all
      four legs incl. macOS).
- [ ] Comfortable that macOS-runner availability/flakiness won't wedge merges;
      if it does, consider keeping only macOS non-blocking and gating Linux.

## Why this is its own branch

Reminder-only so the follow-up isn't forgotten; the actual one-line edit lands
after #427 merges (this branch is cut from `master`, which doesn't yet have the
`os-matrix` job).
