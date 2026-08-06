"""
Tests for scripts/patch_docs_nav.py.

`classify_new` decides which vast-ai/docs navigation group a newly generated
CLI/SDK page lands in. Two properties make it worth pinning:

  * Its return values are exact-match keys into docs.json's `group` names, so
    they are a cross-repo contract. A group renamed upstream used to be
    swallowed by a silent fallback that rehomed every new page into whichever
    managed group sorted first, with CI staying green.
  * Its rules are an ordered if-chain where the order is load-bearing:
    `search-invoices` must reach the `search-` rule before the `invoice` one,
    `show-endpt-instances` must reach the Serverless rules before the
    `instance` one. Nothing but ordering enforces that, so a rule inserted in
    the wrong place silently reroutes existing pages.

The name->group table below is not invented: every row is a page that
vast-ai/docs already publishes under that exact group, so the table asserts
`classify_new` agrees with the shipped navigation.

These exercise pure functions and synthetic docs.json fixtures, so they need
neither a clone of the docs repo nor an installed `vastai`.
"""

import ast
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load_patcher():
    path = SCRIPTS_DIR / "patch_docs_nav.py"
    spec = importlib.util.spec_from_file_location("patch_docs_nav", path)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so annotations resolve through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


nav = _load_patcher()


# ---------------------------------------------------------------------------
# classify_new returns group names docs.json actually has
# ---------------------------------------------------------------------------

# (page stem, group vast-ai/docs publishes it under)
PUBLISHED_PLACEMENTS = [
    ("clone-volume", "Volumes"),
    ("create-api-key", "Accounts"),
    ("create-endpoint", "Serverless"),
    ("create-instance", "Instances"),
    ("create-instances", "Instances"),
    ("create-team", "Teams"),
    ("create-team-role", "Teams"),
    ("create-volume", "Volumes"),
    ("create-workergroup", "Serverless"),
    ("delete-api-key", "Accounts"),
    ("delete-deployment", "Serverless"),
    ("delete-endpoint", "Serverless"),
    ("delete-scheduled-job", "Serverless"),
    ("delete-volume", "Volumes"),
    ("delete-workergroup", "Serverless"),
    ("destroy-instance", "Instances"),
    ("destroy-instances", "Instances"),
    ("destroy-team", "Teams"),
    ("generate-pdf-invoices", "Billing"),
    ("get-endpt-logs", "Serverless"),
    ("get-wrkgrp-logs", "Serverless"),
    ("label-instance", "Instances"),
    ("launch-instance", "Instances"),
    ("list-volume", "Volumes"),
    ("list-volumes", "Volumes"),
    ("metrics-gpu", "Host"),
    ("metrics-gpu-locations", "Host"),
    ("metrics-gpu-trends", "Host"),
    ("prepay-instance", "Instances"),
    ("reboot-instance", "Instances"),
    ("recycle-instance", "Instances"),
    ("remove-team-role", "Teams"),
    ("reset-api-key", "Accounts"),
    ("search-benchmarks", "Search & templates"),
    ("search-invoices", "Search & templates"),
    ("search-offers", "Search & templates"),
    ("search-templates", "Search & templates"),
    ("search-volumes", "Search & templates"),
    ("self-test-machine", "Host"),
    ("set-api-key", "Accounts"),
    ("show-api-key", "Accounts"),
    ("show-deployment", "Serverless"),
    ("show-deployment-versions", "Serverless"),
    ("show-deployments", "Serverless"),
    ("show-endpoints", "Serverless"),
    ("show-instance", "Instances"),
    ("show-instances", "Instances"),
    ("show-instances-v1", "Instances"),
    ("show-invoices", "Billing"),
    ("show-invoices-v1", "Billing"),
    ("show-scheduled-jobs", "Serverless"),
    ("show-team-role", "Teams"),
    ("show-team-roles", "Teams"),
    ("show-volumes", "Volumes"),
    ("show-workergroups", "Serverless"),
    ("start-instance", "Instances"),
    ("start-instances", "Instances"),
    ("stop-instance", "Instances"),
    ("stop-instances", "Instances"),
    ("unlist-volume", "Volumes"),
    ("update-endpoint", "Serverless"),
    ("update-instance", "Instances"),
    ("update-team-role", "Teams"),
    ("update-workergroup", "Serverless"),
]


@pytest.mark.parametrize("name,expected", PUBLISHED_PLACEMENTS)
def test_classify_new_matches_published_navigation(name, expected):
    """Placement must agree with the group vast-ai/docs already ships."""
    assert nav.classify_new(name) == expected


def test_every_classified_name_lands_in_a_known_group():
    """A returned name that isn't in GROUPS has no docs.json group to match."""
    for name, _expected in PUBLISHED_PLACEMENTS:
        assert nav.classify_new(name) in nav.GROUPS


def test_default_group_is_itself_a_known_group():
    """The fallback bucket has to exist, or every unclassified page misfiles."""
    assert nav.DEFAULT_GROUP in nav.GROUPS


def test_no_rule_returns_a_group_outside_groups():
    """Total check over the source, not just the table above.

    The table can only cover names someone thought to list; reading the return
    literals straight out of `classify_new` catches a newly added rule that
    names a group `GROUPS` (and therefore docs.json) doesn't have.
    """
    source = (SCRIPTS_DIR / "patch_docs_nav.py").read_text()
    tree = ast.parse(source)
    func = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "classify_new")

    returned = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                returned.add(node.value.value)

    assert returned, "no string returns found — did classify_new get rewritten?"
    assert returned <= nav.GROUPS, (
        f"classify_new returns group(s) missing from GROUPS: "
        f"{sorted(returned - nav.GROUPS)}"
    )


def test_tfa_family_goes_to_accounts():
    for name in ("tfa-activate", "tfa-totp-setup", "tfa-status", "tfa-delete"):
        assert nav.classify_new(name) == "Accounts"


def test_price_increase_family_goes_to_instances():
    for name in ("accept-price-increase", "reject-price-increase",
                 "show-pending-price-increases"):
        assert nav.classify_new(name) == "Instances"


def test_unrecognized_name_has_no_rule():
    """No rule is the documented path to DEFAULT_GROUP, not an error."""
    assert nav.classify_new("show-machines") is None
    assert nav.classify_new("wholly-unknown-command") is None


# ---------------------------------------------------------------------------
# Rule ordering — each case would flip if a rule moved
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,expected,shadowed_by", [
    # `search-` outranks the substring rules for Billing and Volumes.
    ("search-invoices", "Search & templates", "the 'invoice' -> Billing rule"),
    ("search-volumes", "Search & templates", "the 'volume' -> Volumes rule"),
    ("search-instances", "Search & templates", "the 'instance' -> Instances rule"),
    # Serverless rules outrank the catch-all `instance` rule.
    ("show-endpt-instances", "Serverless", "the 'instance' -> Instances rule"),
    ("show-deployment-instances", "Serverless", "the 'instance' -> Instances rule"),
    # `cluster` covers the longer exact name that used to be spelled out.
    ("remove-machine-from-cluster", "Host", "nothing — it needs the substring rule"),
    # Scheduled jobs are Serverless, not Accounts.
    ("create-scheduled-job", "Serverless", "an 'Accounts' reading of scheduled jobs"),
    ("update-scheduled-job", "Serverless", "an 'Accounts' reading of scheduled jobs"),
])
def test_rule_precedence(name, expected, shadowed_by):
    got = nav.classify_new(name)
    assert got == expected, (
        f"{name!r} classified as {got!r}, expected {expected!r} — "
        f"a rule was probably reordered past {shadowed_by}"
    )


# ---------------------------------------------------------------------------
# patch_docs_nav placement behaviour
# ---------------------------------------------------------------------------

def _docs(groups):
    """Build a minimal docs.json whose nav has one group per (name, prefix).

    Each group is seeded with a page under its own prefix so it clears the
    >=70% managed-group threshold.
    """
    nav_groups = []
    for group_name, prefix in groups:
        nav_groups.append({
            "group": group_name,
            "pages": [f"{prefix}__seed-{group_name.lower().replace(' ', '-')}"],
        })
    return {"navigation": {"tabs": [{"tab": "Reference", "groups": nav_groups}]}}


def _manifest(*names_and_kinds):
    return {"files": [{"name": n, "kind": k} for n, k in names_and_kinds]}


def _seeds(docs):
    """Every seed page, so tests can treat them as pre-existing nav entries."""
    out = []
    for grp, _prefix in nav.iter_managed_groups(docs["navigation"]):
        out.extend(p for p in grp["pages"] if "__seed-" in p)
    return out


def _full_docs():
    return _docs([(g, p) for g in sorted(nav.GROUPS)
                  for p in (nav.CLI_PREFIX, nav.SDK_PREFIX)])


def _placed_in(docs, page):
    for grp, _prefix in nav.iter_managed_groups(docs["navigation"]):
        if page in grp["pages"]:
            return grp["group"]
    return None


def test_new_page_lands_in_its_classified_group():
    docs = _full_docs()
    manifest = _manifest(("create-volume", "cli"))
    manifest["files"].extend({"name": s.split("/")[-1], "kind": "cli"}
                             for s in _seeds(docs) if s.startswith(nav.CLI_PREFIX))
    manifest["files"].extend({"name": s.split("/")[-1], "kind": "sdk"}
                             for s in _seeds(docs) if s.startswith(nav.SDK_PREFIX))

    summary = nav.patch_docs_nav(docs, manifest)

    assert _placed_in(docs, nav.CLI_PREFIX + "create-volume") == "Volumes"
    assert summary["unknown_group"] == []
    assert summary["uncategorized"] == []


def test_unclassified_page_goes_to_default_group_and_warns():
    """Never silently orphaned — visible in nav, and flagged for a rule."""
    docs = _full_docs()
    manifest = _manifest(("show-machines", "cli"))
    manifest["files"].extend({"name": s.split("/")[-1], "kind": "cli"}
                             for s in _seeds(docs) if s.startswith(nav.CLI_PREFIX))
    manifest["files"].extend({"name": s.split("/")[-1], "kind": "sdk"}
                             for s in _seeds(docs) if s.startswith(nav.SDK_PREFIX))

    summary = nav.patch_docs_nav(docs, manifest)

    page = nav.CLI_PREFIX + "show-machines"
    assert _placed_in(docs, page) == nav.DEFAULT_GROUP
    assert page in summary["uncategorized"]
    assert summary["missing_from_nav"] == []


def test_unknown_group_is_reported_not_silently_rehomed():
    """The regression this guards: a group renamed upstream used to fall back
    to the alphabetically-first managed group with no report at all."""
    # Volumes is absent, so classify_new("create-volume") -> "Volumes" cannot
    # be honoured.
    docs = _docs([(g, nav.CLI_PREFIX) for g in sorted(nav.GROUPS - {"Volumes"})])
    manifest = _manifest(("create-volume", "cli"))
    manifest["files"].extend({"name": s.split("/")[-1], "kind": "cli"}
                             for s in _seeds(docs))

    summary = nav.patch_docs_nav(docs, manifest)

    page = nav.CLI_PREFIX + "create-volume"
    assert summary["unknown_group"] == [(page, "Volumes")]
    # Still visible rather than orphaned, but no longer silent.
    assert _placed_in(docs, page) is not None
    assert summary["missing_from_nav"] == []


def test_unknown_group_makes_the_cli_exit_nonzero(tmp_path, monkeypatch, capsys):
    """The exit code is the CI gate, so pin it rather than just the summary."""
    docs = _docs([(g, nav.CLI_PREFIX) for g in sorted(nav.GROUPS - {"Volumes"})])
    manifest = _manifest(("create-volume", "cli"))
    manifest["files"].extend({"name": s.split("/")[-1], "kind": "cli"}
                             for s in _seeds(docs))

    docs_json = tmp_path / "docs.json"
    manifest_json = tmp_path / "manifest.json"
    docs_json.write_text(json.dumps(docs))
    manifest_json.write_text(json.dumps(manifest))
    before = docs_json.read_text()

    monkeypatch.setattr(sys, "argv", [
        "patch_docs_nav.py",
        "--docs-json", str(docs_json),
        "--manifest", str(manifest_json),
    ])

    assert nav.main() == 2
    out = capsys.readouterr().out
    assert "ERROR" in out and "Volumes" in out
    # A contract break must not write a half-right navigation.
    assert docs_json.read_text() == before


def test_stale_pages_are_dropped_but_preserved_pages_survive():
    docs = _docs([("Instances", nav.CLI_PREFIX), ("Instances", nav.SDK_PREFIX)])
    # Register a page that the manifest won't contain, plus a preserved one.
    sdk_group = [g for g, p in nav.iter_managed_groups(docs["navigation"])
                 if p == nav.SDK_PREFIX][0]
    sdk_group["pages"].extend([nav.SDK_PREFIX + "retired-method", "sdk/python/reference/vastai"])
    manifest = _manifest(*[(s.split("/")[-1], "cli" if s.startswith(nav.CLI_PREFIX) else "sdk")
                           for s in _seeds(docs)])

    summary = nav.patch_docs_nav(docs, manifest)

    assert nav.SDK_PREFIX + "retired-method" in summary["removed"]
    assert "sdk/python/reference/vastai" in sdk_group["pages"]
    assert summary["unexpected_in_nav"] == []


def test_patch_is_idempotent():
    docs = _full_docs()
    manifest = _manifest(("create-volume", "cli"), ("show-machines", "cli"))
    manifest["files"].extend({"name": s.split("/")[-1], "kind": "cli"}
                             for s in _seeds(docs) if s.startswith(nav.CLI_PREFIX))
    manifest["files"].extend({"name": s.split("/")[-1], "kind": "sdk"}
                             for s in _seeds(docs) if s.startswith(nav.SDK_PREFIX))

    nav.patch_docs_nav(docs, manifest)
    first = json.dumps(docs, sort_keys=True)
    second_summary = nav.patch_docs_nav(docs, manifest)

    assert json.dumps(docs, sort_keys=True) == first
    assert second_summary["added"] == []
    assert second_summary["removed"] == []


def test_no_managed_groups_is_a_hard_error():
    """A docs.json schema change must fail loudly, not patch nothing."""
    docs = {"navigation": {"tabs": [{"tab": "Guides",
                                     "groups": [{"group": "Guides",
                                                 "pages": ["guides/intro"]}]}]}}
    with pytest.raises(RuntimeError, match="No managed navigation groups"):
        nav.patch_docs_nav(docs, _manifest(("create-volume", "cli")))
