# Design: `curl | bash` Installer for the Vast CLI

```
curl -fsSL https://vast.ai/install.sh | bash
```

`pip install vastai` stays the documented method until the installer passes
testing. This splits the audience (CLI users vs. SDK users); it does not
replace pip.

### Current flow (post-activation)

```
curl -fsSL https://vast.ai/install.sh | bash
        │
        ▼
  install.sh ──fetch──► manifest.{json,env}      (stable script + per-release manifest:
  (no versions,         latest ver · py 3.12 pin ·  script holds no version/URLs, so it's
   no URLs)             per-platform uv + sha256)   written once and rarely touched)
        │
        ▼  glibc ≥2.31 / musl check → pinned uv → managed CPython 3.12 → vastai wheel
           (unsupported platform / bad hash bails to pip before anything lands)
        │
        ▼
  $XDG_DATA_HOME/vastai/            (~/.local/share/vastai, or $VASTAI_INSTALL_DIR)
   ├── bin/vastai → ../current/bin/vastai   (fixed symlink, never retargeted)
   ├── bin/uv                                ~/.local/bin/vastai → bin/vastai  (on PATH)
   ├── current/                              (single active venv; update = build temp → verify → swap)
   └── python/                               (uv-managed CPython 3.12, shared)

  ~/.config/vastai/        vast_api_key, etc. — untouched by install/uninstall
  ~/.cache/vastai/         disposable (uv-pruned after each update)
  ~/.local/state/vastai/   update_check.json (nudge throttle)
        │
        ▼
  vastai update                  ──manifest──►  build temp venv → verify runs → atomic rename
  (registered in main.py;        `--version X` pins or rolls back (same code path);
   passive nudge enabled as      pip installs refused with the pip hint, never touched
   a pre-command hook, §7)
```

## 1. Goals

- Install the CLI with **no system Python, pip, or sudo** required. Fresh VMs
  and CI runners frequently have no usable Python — for a GPU cloud this is the
  common case.
- Decouple the CLI from the user's Python environment (avoid PEP 668 refusals,
  venv confusion, pinned-dependency conflicts on `cryptography`/`pillow`).
- Provide a first-class `vastai update` so the CLI can ship — and users can
  adopt — daily releases (pip already lets us release daily; the gap is that
  users lag, so the fixes never land).

## 2. Core architecture: one-time install script + per-release manifest

The design splits the install into two layers:

- **`install.sh` — a one-time install script** with **no version numbers and
  no artifact URLs**. It only: detects platform → fetches the manifest →
  verifies sha256 → bootstraps + symlinks. "One-time" is about *change
  frequency*: per-release churn lives in the manifest, so the script is written
  once and rarely touched.
- **`manifest.{json,env}` — regenerated every release.** Carries the latest
  version, the CPython pin, and per-platform `uv` URLs + sha256.
  `manifest.json` is for `vastai update`; flat `manifest.env` is for
  `install.sh` (bare machines have no JSON parser).

### Install bootstrap sequence

1. Detect platform (os/arch, musl).
2. Fetch manifest over TLS.
3. Verify sha256 **before** anything lands in `$ROOT`.
4. Install + symlink: pinned `uv` provisions managed CPython 3.12 and installs
   the release wheel — fetched from the same GitHub Release as the manifest
   and verified against its sha256, so a just-published release is installable
   immediately (no PyPI index propagation window) — into an isolated venv.
   **System Python is never used, even if present.**

### Fail-closed guarantees

- Whole script wrapped in `main()`, invoked on the **last line** — a truncated
  download executes nothing.
- TLS-only downloads; uv tarball sha256 verified against the manifest before
  unpacking. The wheel is hash-pinned too: uv verifies the manifest's sha256
  via the `#sha256=` URL fragment. (Version-pinned installs fall back to the
  PyPI pin: uv's TLS + index hashes.)
- Runs as root without complaint (no shared prefix — everything lands in the
  invoking user's `$HOME/.local/share/vastai`), since fresh VMs/containers are
  commonly root.
- Unsupported platform, **glibc older than the floor** (2.31 — Ubuntu 20.04+/
  Debian 11+), or bad hash → exits cleanly pointing at pip, before anything
  lands in `$ROOT`.
- PATH/completion edits default-on at a real TTY (no prompt, like uv/rustup);
  skippable via `--no-modify-path`, never written non-interactively.
- pip coexistence: pip stays the channel for the Python SDK, and its package
  ships a `vastai` script too — the `vastai` *command* belongs to the managed
  install. The rc gets one constant line sourcing `<data-root>/env.sh` (the
  rustup/uv pattern), which prepends `~/.local/bin` unless already first — so
  precedence is asserted at every shell startup and a later pip install is
  out-ranked without any re-run. rc files are append-only, never rewritten;
  the coexistence warning prints only when the rc line couldn't be written
  (non-interactive, `--no-modify-path`, unknown shell).

## 3. On-disk layout

Layout follows the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/latest/)
instead of a single ad hoc dotfolder. Four roots, each independently
overridable by the standard `XDG_*` variable, plus `VASTAI_INSTALL_DIR` as a
dedicated override for the program root (also the sandboxing knob the
hermetic tests use):

| Purpose | Default | Override |
|---|---|---|
| Program (venv, bootstrap engine, managed CPython) | `~/.local/share/vastai` | `VASTAI_INSTALL_DIR`, else `$XDG_DATA_HOME` |
| Config (e.g. `vast_api_key`) | `~/.config/vastai` | `$XDG_CONFIG_HOME` |
| Cache (disposable, regenerable) | `~/.cache/vastai` | `$XDG_CACHE_HOME` |
| State (update-check throttle) | `~/.local/state/vastai` | `$XDG_STATE_HOME` |
| Binary symlink | `~/.local/bin/vastai` | (fixed — always here, matches every other XDG-aware CLI) |

```
~/.local/share/vastai/            ($XDG_DATA_HOME/vastai, or $VASTAI_INSTALL_DIR)
├── bin/
│   ├── vastai   → ../current/bin/vastai   (fixed symlink; target never changes)
│   └── uv                                  (pinned bootstrap engine, internal)
├── current/                                (the single active venv — see §6)
├── env.sh                                  (sourced by the rc line: PATH precedence + completion)
└── python/                                 (uv-managed CPython 3.12, shared)

~/.config/vastai/                 vast_api_key, etc. — untouched by install/uninstall
~/.cache/vastai/                  disposable (e.g. a future download cache, §6)
~/.local/state/vastai/            update_check.json (throttle timestamp)
```

- The venv is built **relocatable** (`uv venv --relocatable`) so its
  entry-point shebangs don't hardcode the build path — that's what lets an
  update build in a temp dir and rename `current/` into place (§6).
- `bin/vastai` is a **fixed** symlink into `current/`; it is created once and
  never retargeted (the `current/` path is constant). `~/.local/bin/vastai` →
  `<data-root>/bin/vastai` puts it on PATH.
- Config lives in `~/.config/vastai` — **untouched** by install/uninstall.
  Switching install methods keeps auth; uninstalling keeps the key.
- Throwaway state (update-check throttle) lives in `~/.local/state/vastai`,
  separate from the disposable-cache directory — it's a small persistent
  marker, not something safe to evict on a whim the way a cache entry is.
- Uninstall: `rm -rf "$XDG_DATA_HOME/vastai" ~/.local/bin/vastai` (default
  `$XDG_DATA_HOME` is `~/.local/share`; use whatever `VASTAI_INSTALL_DIR`/
  `XDG_DATA_HOME` you installed with, if overridden. Config, cache, and state
  are left alone, same as before).

This is a directory-naming change only — see §14 for why it does **not**
reopen the single-active-install decision in §6: `current/` still names the
one active venv, not a slot in a retained version tree.

### Detecting a managed install

`vastai update` decides "do I own this install?" **structurally**, not from a
marker file: a managed CLI runs from `<data-root>/current` with a sibling
`<data-root>/bin/uv`. That's ground truth — `sys.prefix` can't drift or be
hand-copied the way a receipt file could. **pip installs run from elsewhere,
fail the check, and are never touched by the updater.** Either misdetection
fails safe (a wrong "managed" hits "no bin/uv" and aborts cleanly; a wrong
"pip" just points you at pip), so no on-disk receipt is needed.

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
`canary` split, no per-channel manifests, no channel tracking. If a
staged-rollout lever is ever wanted, a second manifest file served at a
different path is the natural seam — but it is explicitly **not** pursued now.

## 6. Update + rollback model

Single active install (the **deno model**): one active venv, replaced in place,
plus a `--version` flag that doubles as rollback. No version tree, no symlink
retargeting, no retention/GC, no offline-instant-rollback guarantee.

### Behavior
- **Single active install.** Update = build-new-then-swap, never mutate in
  place destructively: build a fresh venv in a temp dir (`.current.new`) →
  verify → atomically rename over `current/`. An interrupted update only ever
  dirties the temp dir; the live `current/` is touched by two renames
  (~instant) and can never be left half-written. **This is the one safety
  property worth preserving.**
- `vastai update` — installs the manifest's latest.
- `vastai update --version X` — installs/pins a specific version. **Downgrade
  and forward-pin are the identical code path**; rollback is just "don't forbid
  downgrades," reusing the same install-and-swap. There is no separate rollback
  machinery and no kept-on-disk previous version.
- Verification mirrors the installer: confirm the new env runs and reports the
  expected version before swapping. Latest installs the manifest's hash-pinned
  release wheel; `--version` pins use the PyPI pin (uv: TLS + index hashes).
  The uv binary itself comes from the manifest sha256 at install time.
- After a successful swap, best-effort `uv cache prune`: envs are hardlinked
  out of uv's user-global cache, which otherwise accumulates every version's
  wheels forever. Prune, never clean — the cache is shared with any other uv
  on the machine — and a prune failure never fails the completed update.

### Same-method discipline
pip installs (which fail the managed-install check) get the correct
`pip install --upgrade vastai` hint and exit — **never shell out to a guessed
pip.** Matches uv's behavior (self-update disabled when installed another way).

### Optional later: download cache
A cache of the last few wheels at `~/.cache/vastai/` would make a re-pin/
rollback fast or offline. It is **a cache, not a version store** — evict
oldest, a miss simply re-fetches, no "don't delete what's running" invariant.
Not built in v1.

## 7. Passive update nudge

> **Status: enabled.** `notify_update(args)` runs as a pre-command hook in
> `main.py`, before the command's own output, so it's never buried underneath
> it. Opt out with `VASTAI_NO_UPDATE_CHECK=1` (also off under
> `--raw`/`CI`/non-TTY).

- Before commands: at most **one manifest GET and one stderr line per 24h**, hard
  1s timeout, every failure silent with 24h backoff (offline machines pay ≤1s
  once/day).
- Suppressed under `--raw`, `CI`, non-TTY, or `VASTAI_NO_UPDATE_CHECK=1`.
- **No telemetry** — the check is a GET of a static file.
- The nudge only ever *suggests*; there is no minimum-version gate and no
  remote-push channel — we never block or force an upgrade.

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
- `VASTAI_INSTALL_DIR` — override the program root (default `$XDG_DATA_HOME/vastai`,
  i.e. `~/.local/share/vastai`).
- `XDG_DATA_HOME` / `XDG_CONFIG_HOME` / `XDG_CACHE_HOME` / `XDG_STATE_HOME` —
  standard XDG overrides for the program/config/cache/state roots (§3).
- `VASTAI_CLI_BASE_URL` — manifest origin (dev/release verification).
- `VASTAI_PIP_SPEC` — dev/CI: install from a local wheel path/URL.
- `VASTAI_GLIBC_FLOOR` — override the minimum-glibc gate (default 2.31).
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
user-facing change. `wheel_url` points installs of `latest` at the wheel on
the same Release — drafted, fully populated, then published, so a manifest
can never advertise a version installers can't fetch. `--no-wheel-url` omits
the field (dev manifests from a placeholder wheel); consumers fall back to
the PyPI version pin, as do `--version` pins and pre-`wheel_url` releases.

## 12. Rollout (dark launch)

Nothing user-visible until the redirects go live; README/docs stay pip-only
until launch.

1. **PR 1 (this PR):** installer scripts, manifest generator, hermetic tests,
   dormant `vastai update` implementation + unit tests, this doc. **No-op for
   the existing CLI** — `main.py` and workflows untouched.
2. **PR 2 (activation):** register the `update` command in `main.py` (the
   passive nudge is wired but left **commented out** — manual `vastai update`
   only for now, §7); add the `scripts/publish_release.py` orchestrator (§13)
   and the release-CI wiring that calls it (attach `manifest.{json,env}` +
   `install.sh` to the GitHub Release; post-publish install smoke test on a
   clean ubuntu runner — macOS deferred; shellcheck + hermetic-test job on PRs).
3. **Tag a release** so `releases/latest` assets exist.
4. **Deploy the `vast_landing` redirects** — the activation point.
5. **Internal testing:** TTY checklist (consent prompts, nudge UX, offline
   behavior); OS matrix (debian-slim no-Python, alpine/musl, old glibc, both
   Darwins); team dogfood across ≥1 release cycle including a real `vastai
   update` and a `--version` downgrade.
6. **Launch:** flip README to split install (CLI via installer, SDK via pip).

## 13. Release runbook

A release is triggered by pushing a `vX.Y.Z` tag — `python-publish.yml` then
publishes to PyPI and attaches the installer assets via `publish_release.py`.
The manual equivalent, for reference / break-glass (~10 min):

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
~/.local/share/vastai/bin/vastai --version
```

Rules the automation must enforce (a human must remember for now):
- **Hash the published wheel**, not a local rebuild (hash won't match what PyPI serves).
- **Normal release only** — drafts/pre-releases are skipped by `releases/latest`,
  so redirects would keep serving the old version.
- **Upload `install.sh` from the tagged commit**, not a dirty working tree.
- Once redirects are live, **the asset upload *is* the deploy** — verify immediately.

### `scripts/publish_release.py` (CI-only orchestrator)

The four rules above are exactly the things a human forgets, so CI owns them:
the script runs only in `python-publish.yml`, right after `poetry publish
--build`, hashing the exact bytes in `dist/` that PyPI serves. It wraps the
existing `make_manifest.py` (no duplicated logic), creates the Release as a
draft, uploads all assets, then flips it live; re-runs use `gh release upload
--clobber`. The workflow step is `python scripts/publish_release.py
"${GITHUB_REF_NAME#v}"`; `--dry-run` prints every action and touches nothing.

The version is always explicit (it's the tag the deployer chose). Computing the
next version from the latest tag (`major|minor|patch`) is deliberately left out
for now — pick the version when you tag.

A local mode (tag → poll PyPI → attach → verify) existed while CI was being
proven and was removed once tag-push releases were the only path used; the
manual runbook above is the break-glass fallback.

(Named `publish_release.py`, not `publish_update.py`: it publishes a *release* —
`install.sh` + both manifests as Release assets — not "an update.")

## 14. Decisions log

- Canonical URL `https://vast.ai/install.sh`; hosting via `vast_landing` 307
  redirects → GitHub Release assets.
- **Layout follows the XDG Base Directory Specification (CLN ticket, this
  PR):** program in `~/.local/share/vastai` (`current/` the single active
  venv), config in `~/.config/vastai`, cache in `~/.cache/vastai`, update-check
  state in `~/.local/state/vastai`, binary symlinked at `~/.local/bin/vastai`
  — each root independently overridable via the standard `XDG_*` variable
  (§3, §10). This was a pure directory-naming migration off the original
  single `~/.vastai` dotfolder: it deliberately does **not** revisit the
  single-active-install decision below — `current/` is still one active venv,
  not a slot in a version tree. Config/cache placement was already
  XDG-correct before this change (via the `xdg` package); state is the only
  new root, split out of cache because a throttle timestamp is small,
  persistent, and not safe to treat as disposable the way a download cache is.
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
- Release orchestration is one script (`scripts/publish_release.py`, §13) run
  by CI on tag push — not orchestration logic spread across YAML. Its former
  local mode was removed once tag-push releases proved out; break-glass is the
  manual runbook.
- **Platform support floor: glibc ≥ 2.31** (Ubuntu 20.04+/Debian 11+). Older
  systems (18.04 = 2.27, CentOS 7 = 2.17) lack wheels for some deps under the
  pinned CPython, so `install.sh` detects glibc and bails cleanly to pip rather
  than failing mid-build. Override with `VASTAI_GLIBC_FLOOR` (also a test seam).
- **musl/Alpine is supported, and that constrains deps.** musl detection keys off
  the `ld-musl-*` loader, not `ldd --version` (musl's `ldd` exits non-zero, which
  `set -o pipefail` turned into a silent mis-detect → glibc uv on musl). Support
  is real only because every native dep ships musllinux wheels — which is why
  `psutil` is pinned `~=7.0` (6.x had no musl wheels). New native deps must have
  musl wheels or alpine breaks; the `installer-ci` OS matrix (incl. `alpine:latest`)
  gates this, triggered on `pyproject.toml` changes.
