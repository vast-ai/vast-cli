# Design: `curl | bash` Installer for the Vast CLI

```
curl -fsSL https://vast.ai/install.sh | bash
```

`pip install vastai` stays the documented method until the installer passes
testing. This splits the audience (CLI users vs. SDK users); it does not
replace pip.

## 1. Goals

- Install the CLI with **no system Python, pip, or sudo** required. Fresh VMs
  and CI runners frequently have no usable Python — for a GPU cloud this is the
  common case.
- Decouple the CLI from the user's Python environment (avoid PEP 668 refusals,
  venv confusion, pinned-dependency conflicts on `cryptography`/`pillow`).
- Provide a real update story (`vastai update`) and a way to signal a minimum
  supported version.

## 2. Core architecture: one-time install script + per-release manifest

The design splits the install into two layers:

- **`install.sh` — a one-time install script** with **no version numbers and
  no artifact URLs**. It only: detects platform → fetches the manifest →
  verifies sha256 → bootstraps + symlinks. "One-time" is about *change
  frequency*: per-release churn lives in the manifest, so the script is written
  once and rarely touched.
- **`manifest.{json,env}` — regenerated every release.** Carries the latest
  version, the CPython pin, per-platform `uv` URLs + sha256, and
  `minimum_version`. `manifest.json` is for `vastai update`; flat `manifest.env`
  is for `install.sh` (bare machines have no JSON parser).

### Install bootstrap sequence

1. Detect platform (os/arch, musl).
2. Fetch manifest over TLS.
3. Verify sha256 **before** anything lands in `$ROOT`.
4. Install + symlink: pinned `uv` provisions managed CPython 3.12 and installs
   the published PyPI wheel into an isolated venv. **System Python is never
   used, even if present.**

### Fail-closed guarantees

- Whole script wrapped in `main()`, invoked on the **last line** — a truncated
  download executes nothing.
- TLS-only downloads; uv tarball sha256 verified against the manifest before
  unpacking. (Wheel integrity is delegated to uv: TLS + PyPI hashes.)
- Runs as root without complaint (no shared prefix — everything lands in the
  invoking user's `$HOME/.vastai`), since fresh VMs/containers are commonly root.
- Unsupported platform or bad hash → exits cleanly pointing at pip.
- PATH/completion edits only with consent at a real TTY; skippable via
  `--no-modify-path`.

## 3. On-disk layout

Everything lives under `~/.vastai` (`VASTAI_INSTALL_DIR` overrides):

```
~/.vastai/
├── bin/
│   ├── vastai   → ../env/bin/vastai   (fixed symlink; target never changes)
│   └── uv                              (pinned bootstrap engine, internal)
├── env/                                (the single active venv — see §6)
├── python/                             (uv-managed CPython 3.12, shared)
└── install-receipt.json
```

- The venv is built **relocatable** (`uv venv --relocatable`) so its
  entry-point shebangs don't hardcode the build path — that's what lets an
  update build in a temp dir and rename `env/` into place (§6).
- `bin/vastai` is a **fixed** symlink into `env/`; it is created once and never
  retargeted (the `env/` path is constant). `~/.local/bin/vastai` →
  `~/.vastai/bin/vastai` puts it on PATH.
- Config lives in `~/.config/vastai` (e.g. `vast_api_key`) — **untouched** by
  install/uninstall. Switching install methods keeps auth; uninstalling keeps
  the key.
- Throwaway state lives in `~/.cache/vastai` (update-check throttle).
- Uninstall: `rm -rf ~/.vastai ~/.local/bin/vastai`.

### `install-receipt.json`

Ground truth that `vastai update` uses to know it owns the install. Records
`method`, `version`, `previous_version`, `python`, `installed_at`. **pip
installs have no receipt and are never touched by the updater.**

## 4. Hosting (decided)

GitHub Releases stores the artifacts; `vast.ai` serves canonical URLs via three
**307 temporary** redirects in `vast_landing` (branch
`feat/cli-installer-redirects`):

| vast.ai path | → GitHub Release asset |
|---|---|
| `/install.sh` | `releases/latest/download/install.sh` |
| `/cli/manifest.json` | `releases/latest/download/manifest.json` |
| `/cli/manifest.env` | `releases/latest/download/manifest.env` |

- **Temporary (307) on purpose:** the published one-liner is sticky forever, so
  the advertised URL must stay repointable (CDN move, repo move) without
  redirect-cache poisoning. A 301 could get cached by intermediaries and lock
  the URL to a stale target.
- `releases/latest` does the per-release work; the landing repo is touched once.

### Abort path

Hosting is three redirects. Remove them and: the installer 404s with a clear
error, update nudges go silent, and **every already-installed CLI keeps
working** (they run from the local install, not the redirect). No client-side
breakage is possible from un-hosting.

## 5. Single channel (latest only)

There is one channel: whatever `releases/latest` points at. No `stable`/`beta`/
`canary` split, no per-channel manifests, no channel field in the receipt. If a
staged-rollout lever is ever wanted, a second manifest file served at a
different path is the natural seam — but it is explicitly **not** pursued now.

## 6. Update + rollback model

Single active install (the **deno model**): one active venv, replaced in place,
plus a `--version` flag that doubles as rollback. No version tree, no symlink
retargeting, no retention/GC, no offline-instant-rollback guarantee.

### Behavior
- **Single active install.** Update = build-new-then-swap, never mutate in
  place destructively: build a fresh venv in a temp dir (`.env.new`) → verify →
  atomically rename over `env/`. An interrupted update only ever dirties the
  temp dir; the live `env/` is touched by two renames (~instant) and can never
  be left half-written. **This is the one safety property worth preserving.**
- `vastai update` — installs the manifest's latest.
- `vastai update --version X` — installs/pins a specific version. **Downgrade
  and forward-pin are the identical code path**; rollback is just "don't forbid
  downgrades," reusing the same install-and-swap. There is no separate rollback
  machinery and no kept-on-disk previous version.
- Verification mirrors the installer: confirm the new env runs and reports the
  expected version before swapping; wheel integrity comes from uv (TLS + PyPI
  hashes), the uv binary itself from the manifest sha256 at install time.

### Why keep `--version` rollback at all
We release **daily**, so bad releases ship fairly often. Without a `--version`
escape hatch a user who pulls a broken daily can only "uninstall, reinstall, and
hope latest is fixed" — useless mid-incident. `--version` lets them pin to
yesterday's known-good. It is cheap insurance *because* we release daily, and it
costs nothing extra on top of single-version (the mechanism already exists for
pinning).

### Same-method discipline
pip installs (no receipt) get the correct `pip install --upgrade vastai` hint
and exit — **never shell out to a guessed pip.** Matches uv's behavior
(self-update disabled when installed another way).

### Optional later: download cache
A cache of the last few wheels at `~/.cache/vastai/` would make a re-pin/
rollback fast or offline. It is **a cache, not a version store** — evict
oldest, a miss simply re-fetches, no "don't delete what's running" invariant.
Not built in v1.

## 7. Passive update nudge

- After commands: at most **one manifest GET and one stderr line per 24h**, hard
  1s timeout, every failure silent with 24h backoff (offline machines pay ≤1s
  once/day).
- Suppressed under `--raw`, `CI`, non-TTY, or `VASTAI_NO_UPDATE_CHECK=1`.
- **No telemetry** — the check is a GET of a static file.
- Manifest `minimum_version` upgrades the nudge to a **warning** (never a hard
  failure) for too-old clients. This is the only "force convergence" lever;
  there is no remote-push channel by design.

Note: `latest` governs what gets **installed** (fresh installs + update checks),
not what gets **run** (the active local install). A hotfix instantly fixes new
installs and gives existing installs a one-command path to the fix, but does not
reach out and patch running CLIs.

## 8. Bug-fix propagation model

Two artifacts with **opposite** update properties:

| | Bug in the **wheel** (CLI) | Bug in **`install.sh`** |
|---|---|---|
| Runs | on every command | once, at install only |
| Affects | everyone on that version | only **new installs**, before the fix is uploaded |
| Fix | hotfix release + manifest bump; existing get it via `vastai update` | upload new `install.sh`; next install gets it instantly |
| Reaches existing installs? | yes (opt-in via update) | **no — and doesn't need to** (they never re-run the script) |

Consequence: keep `install.sh` as **thin** as possible and push everything that
might need post-install fixing (update logic, nudge) into the wheel
(`selfupdate.py`) — the script is the one component you can't retroactively patch
on existing machines, and its only audience is fresh installs who always fetch
it fresh.

## 9. Signing (deferred, but know the bar)

Manifest signing (minisign/Sigstore) is a deliberate later-phase option, fine to
ship v1 without. But be clear-eyed: sha256-in-manifest protects against
corruption-in-transit and a tampered *artifact* — it does nothing if an attacker
can rewrite the *manifest itself* (they'd put their own hash in). The current
trust chain rests on TLS + "GitHub Releases not compromised." Signing the
manifest closes that gap. Relevant because the CLI holds API keys — don't let
"we verify sha256" imply the supply chain is signed; it isn't until the manifest
is.

## 10. Env knobs

- `VASTAI_VERSION` — pin version (also the rollback/downgrade mechanism).
- `VASTAI_INSTALL_DIR` — override `~/.vastai`.
- `VASTAI_CLI_BASE_URL` — manifest origin (dev/release verification).
- `VASTAI_PIP_SPEC` — dev/CI: install from a local wheel path/URL.
- `VASTAI_NO_UPDATE_CHECK=1` — suppress the nudge.
- `--no-modify-path` — skip PATH/completion edits.

*Future ergonomic win:* consolidate the CI/ephemeral story into one documented
switch (uv does this with `UV_UNMANAGED_INSTALL`: custom path + no profile mods
+ self-update disabled). The pieces exist scattered; one "hermetic CI mode" var
is what CI users will reach for by analogy to uv.

## 11. Manifest generation

`scripts/make_manifest.py` (stdlib-only) renders both forms from a released
wheel. Pins the `uv` version and embeds per-platform sha256 fetched from uv's
release assets — no floating tags anywhere in the supply chain. `install.type`
is the seam that lets a frozen binary replace the wheel later with zero
user-facing change; a future `wheel_url` field would let the CLI ship faster
than the PyPI `vastai` package (attach the wheel to the Release, point installs
there) — not enabled yet, one pipeline at a time.

## 12. Rollout (dark launch)

Nothing user-visible until the redirects go live; README/docs stay pip-only
until launch.

1. **PR 1 (this PR):** installer scripts, manifest generator, hermetic tests,
   dormant `vastai update` implementation + unit tests, this doc. **No-op for
   the existing CLI** — `main.py` and workflows untouched.
2. **PR 2 (activation):** register `update` + nudge in `main.py`; add the
   `scripts/publish_release.py` orchestrator (§13) and the release-CI wiring
   that calls it (attach `manifest.{json,env}` + `install.sh` to the GitHub
   Release; post-publish install smoke test on clean ubuntu/macos runners;
   shellcheck + hermetic-test job on PRs).
3. **Tag a release** so `releases/latest` assets exist.
4. **Deploy the `vast_landing` redirects** — the activation point.
5. **Internal testing:** TTY checklist (consent prompts, nudge UX, offline
   behavior); OS matrix (debian-slim no-Python, alpine/musl, old glibc, both
   Darwins); team dogfood across ≥1 release cycle including a real `vastai
   update` and a `--version` downgrade.
6. **Launch:** flip README to split install (CLI via installer, SDK via pip).

## 13. Release runbook (manual until the activation PR automates it)

PyPI publishing stays automated (`python-publish.yml` on tag push). Manual for
now is the installer side. ~10 min:

```bash
git tag v1.0.14 && git push origin v1.0.14         # existing CI publishes to PyPI

# hash the *published* wheel, never a local rebuild (rebuilds aren't byte-identical)
pip download vastai==1.0.14 --no-deps -d /tmp/rel/
python3 scripts/make_manifest.py --version 1.0.14 \
    --wheel '/tmp/rel/vastai-1.0.14-*.whl' --out /tmp/rel/m/

gh release create v1.0.14 --title v1.0.14 --notes "vastai 1.0.14"
gh release upload v1.0.14 --clobber \
    /tmp/rel/m/manifest.json /tmp/rel/m/manifest.env scripts/install.sh

# verify the real user path before walking away
VASTAI_CLI_BASE_URL=https://github.com/vast-ai/vast-cli/releases/latest/download \
    bash scripts/install.sh
~/.vastai/bin/vastai --version
```

Rules the automation must enforce (a human must remember for now):
- **Hash the published wheel**, not a local rebuild (hash won't match what PyPI serves).
- **Normal release only** — drafts/pre-releases are skipped by `releases/latest`,
  so redirects would keep serving the old version.
- **Upload `install.sh` from the tagged commit**, not a dirty working tree.
- Once redirects are live, **the asset upload *is* the deploy** — verify immediately.

### Planned: `scripts/publish_release.py` (one orchestrator, human + CI)

The four rules above are exactly the things a human forgets, so the runbook
collapses into a single script — built as **one orchestrator both a human and
CI invoke**, so the dangerous steps have one implementation, not a local copy
plus a divergent YAML copy. Slated for **PR 2 (activation)**, not this PR, since
it is activation machinery (keeps this PR a no-op for the existing CLI).

```bash
scripts/publish_release.py 1.0.14            # local: tag → wait for PyPI → manifest → gh release → verify
scripts/publish_release.py 1.0.14 --ci       # CI: hash dist/*.whl → manifest → attach (tag/poll skipped)
scripts/publish_release.py 1.0.14 --dry-run  # print every action, touch nothing
```

It wraps the existing `make_manifest.py` (no duplicated logic) and differs only
by context:

| | Local (manual window) | CI (`--ci`, on tag push) |
|---|---|---|
| Tag | script pushes it | already pushed (the trigger) |
| Wheel to hash | `pip download` from PyPI after publish — **polls** until available | `dist/*.whl` from `poetry publish --build` — the exact published bytes, no wait |
| `gh` auth | developer creds | `GITHUB_TOKEN` |

Guardrails (because it triggers irreversible, outward actions): refuse on a
dirty tree / wrong branch; refuse if the tag already exists (re-runs use
`gh release upload --clobber`); confirm before the tag push and
`gh release create` unless `--yes`/`--ci`; baked-in post-upload verification
(install via the Release URL → `vastai --version`). PR 2's workflow step then
reduces to `python scripts/publish_release.py "${GITHUB_REF_NAME#v}" --ci`.

(Named `publish_release.py`, not `publish_update.py`: it publishes a *release* —
`install.sh` + both manifests as Release assets — not "an update.")

## 14. Decisions log

- Canonical URL `https://vast.ai/install.sh`; hosting via `vast_landing` 307
  redirects → GitHub Release assets.
- Program in `~/.vastai`, config in `~/.config/vastai`, throwaway state in
  `~/.cache/vastai`.
- Managed runtime pinned to CPython 3.12 (independent of the wheel's `>=3.10`
  for pip users); bumps roll out as manifest changes.
- Bootstrap engine: pinned `uv` behind the manifest seam — replaceable without
  user impact. Venv built `--relocatable` so the build-temp-then-rename swap works.
- **Update model: single active install, replace-in-place (build temp → verify →
  rename), rollback via `vastai update --version X`. Side-by-side versions /
  symlink tree / GC explicitly dropped.** Optional download cache later.
- Single channel (latest only); no channel machinery.
- Update nudges are same-method only (pip users told pip); cross-promoting the
  installer to pip users deferred to post-launch.
- Frozen binaries, a Windows installer, and manifest signing (minisign/Sigstore)
  are explicit later-phase options.
- No guard against downgrading below the first update-capable release —
  deliberate: low-probability, low-severity; recovery is a reinstall.
- Release orchestration is one script (`scripts/publish_release.py`, §13) shared
  by humans and CI — not a local helper plus a separate CI YAML copy. Lands in
  PR 2 to keep PR 1 a no-op.
