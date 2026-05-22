#!/usr/bin/env python3
"""
Patch vast-ai/docs `docs.json` navigation so it stays in lockstep with the
CLI/SDK MDX files that ``generate_cli_sdk_docs.py`` wrote.

Mintlify only renders pages that are registered in the navigation tree;
without this step, generated pages exist on disk as orphans and the
Mintlify preview shows "No changes to preview".

Algorithm:

  1. Walk docs.json's navigation tree.  A "managed group" is one whose
     pages list is dominated (>=70%) by entries starting with
     ``cli/reference/`` or ``sdk/python/reference/``.
  2. Within each managed group, drop entries that are no longer in the
     generator manifest (stale pages) — except for an explicit preserve
     list (the SDK overview page, etc.).
  3. Any page in the manifest that is not already registered under SOME
     managed group with the matching prefix gets placed into the
     semantically-appropriate group via ``classify_new``.
  4. Sort each managed group's string entries alphabetically so the diff
     is deterministic; preserve any non-string entries (subgroups,
     anchors) in their original order.

Usage:

    python scripts/patch_docs_nav.py \\
        --docs-json /path/to/docs-repo/docs.json \\
        --manifest manifest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable


CLI_PREFIX = "cli/reference/"
SDK_PREFIX = "sdk/python/reference/"

# Pages we never auto-manage.  These are hand-authored and should stay in
# the navigation even though the generator doesn't produce them.
PRESERVE = {
    "sdk/python/reference/vastai",  # SDK overview page
}

# A nav group is "managed" if at least this fraction of its string-page
# entries fall under one of our auto-managed prefixes.  70% leaves room
# for the occasional hand-curated cross-link without classifying that
# group as managed.
MANAGED_GROUP_THRESHOLD = 0.7


def classify_new(name: str) -> str | None:
    """Return the group name a new page should be placed into.

    ``name`` is the bare filename stem (no prefix, no extension), e.g.
    ``tfa-activate`` or ``add-network-disk``.  Returns ``None`` when no
    rule matches — caller should warn and skip placement so editorial
    can categorize manually.

    Rules are ordered most-specific-first.  When adding new commands
    that don't fit, extend this function rather than papering over with
    a default bucket.
    """
    if name.startswith("tfa-"):
        return "Accounts"
    if name.endswith("-api-key"):
        return "Accounts"
    if "scheduled-job" in name:
        return "Accounts"
    if "invoice" in name or name == "fetch-contracts":
        return "Billing"
    if "team" in name:
        return "Teams"
    if "network-disk" in name or "network-volume" in name or "network-volumes" in name:
        return "Volumes"
    if "cluster" in name or "overlay" in name or name == "remove-machine-from-cluster":
        return "Host"
    if name.startswith("search-"):
        return "Search & templates"
    if "endpt" in name or "endpoint" in name or "workergroup" in name or "wrkgrp" in name:
        return "Serverless"
    if (
        "instance" in name
        or name == "take-snapshot"
        or name == "show-instance-filters"
        or name == "accept-price-increase"
    ):
        return "Instances"
    return None


def iter_managed_groups(node) -> Iterable[tuple[dict, str]]:
    """Yield (group_dict, prefix) for every navigation group whose pages
    are predominantly under one of our managed prefixes."""
    if isinstance(node, list):
        for item in node:
            if (isinstance(item, dict)
                    and "group" in item
                    and isinstance(item.get("pages"), list)):
                strs = [p for p in item["pages"] if isinstance(p, str)]
                if strs:
                    cli_share = sum(1 for s in strs if s.startswith(CLI_PREFIX)) / len(strs)
                    sdk_share = sum(1 for s in strs if s.startswith(SDK_PREFIX)) / len(strs)
                    if cli_share >= MANAGED_GROUP_THRESHOLD:
                        yield item, CLI_PREFIX
                    elif sdk_share >= MANAGED_GROUP_THRESHOLD:
                        yield item, SDK_PREFIX
            if isinstance(item, dict):
                for v in item.values():
                    yield from iter_managed_groups(v)
            elif isinstance(item, list):
                yield from iter_managed_groups(item)
    elif isinstance(node, dict):
        for v in node.values():
            yield from iter_managed_groups(v)


def patch_docs_nav(docs: dict, manifest: dict) -> dict:
    """Mutate ``docs`` in place to reflect ``manifest``.  Returns a
    summary dict with counts and any uncategorized pages."""
    gen_cli = {CLI_PREFIX + f["name"] for f in manifest["files"] if f["kind"] == "cli"}
    gen_sdk = {SDK_PREFIX + f["name"] for f in manifest["files"] if f["kind"] == "sdk"}
    manifest_all = gen_cli | gen_sdk

    managed = list(iter_managed_groups(docs["navigation"]))
    if not managed:
        raise RuntimeError(
            "No managed navigation groups found in docs.json — did the "
            "schema change?  Expected at least one group whose pages are "
            f">={int(MANAGED_GROUP_THRESHOLD * 100)}% cli/reference/* or sdk/python/reference/*."
        )

    # Where does each existing page live?  Pages not in this map are
    # candidates for placement via classify_new.
    existing_loc: dict[str, dict] = {}
    for grp, _prefix in managed:
        for p in grp["pages"]:
            if isinstance(p, str):
                existing_loc[p] = grp

    # Step 1: drop stale entries from each managed group.
    removed: list[str] = []
    for grp, prefix in managed:
        kept = []
        for p in grp["pages"]:
            if isinstance(p, str) and p.startswith(prefix):
                if p in manifest_all or p in PRESERVE:
                    kept.append(p)
                else:
                    removed.append(p)
            else:
                # Non-prefix strings and subgroups stay put
                kept.append(p)
        grp["pages"] = kept

    # Step 2: place new entries.
    groups_by_key: dict[tuple[str, str], dict] = {
        (g["group"], prefix): g for g, prefix in managed
    }
    added: list[str] = []
    uncategorized: list[str] = []
    for full in sorted(manifest_all):
        if full in existing_loc:
            continue
        name = full.rsplit("/", 1)[-1]
        prefix = CLI_PREFIX if full.startswith(CLI_PREFIX) else SDK_PREFIX
        group_name = classify_new(name)
        if group_name is None:
            uncategorized.append(full)
            continue
        grp = groups_by_key.get((group_name, prefix))
        if grp is None:
            uncategorized.append(full)
            continue
        grp["pages"].append(full)
        added.append(full)

    # Step 3: sort string entries within each managed group for a stable
    # diff.  Non-string entries (subgroups, anchors) keep their order.
    for grp, _prefix in managed:
        strs = sorted([p for p in grp["pages"] if isinstance(p, str)])
        others = [p for p in grp["pages"] if not isinstance(p, str)]
        grp["pages"] = strs + others

    # Sanity check: every manifest page must end up in nav, every
    # remaining nav-string page must be in the manifest (or in PRESERVE).
    final_cli: set[str] = set()
    final_sdk: set[str] = set()
    def collect(n):
        if isinstance(n, list):
            for i in n:
                if isinstance(i, str):
                    if i.startswith(CLI_PREFIX):
                        final_cli.add(i)
                    elif i.startswith(SDK_PREFIX):
                        final_sdk.add(i)
                else:
                    collect(i)
        elif isinstance(n, dict):
            for v in n.values():
                collect(v)
    collect(docs["navigation"])

    missing = (gen_cli - final_cli) | (gen_sdk - final_sdk)
    unexpected = ((final_cli | final_sdk) - manifest_all) - PRESERVE
    # Uncategorized pages aren't in nav by design (they were skipped) —
    # don't flag those as "missing"
    missing -= set(uncategorized)

    return {
        "managed_groups": len(managed),
        "added": added,
        "removed": removed,
        "uncategorized": uncategorized,
        "missing_from_nav": sorted(missing),
        "unexpected_in_nav": sorted(unexpected),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--docs-json", required=True, type=Path,
                    help="Path to docs.json in a clone of vast-ai/docs")
    ap.add_argument("--manifest", required=True, type=Path,
                    help="Path to manifest.json from generate_cli_sdk_docs.py")
    ap.add_argument("--check", action="store_true",
                    help="Don't write; exit non-zero if changes would be made")
    args = ap.parse_args()

    docs = json.loads(args.docs_json.read_text())
    manifest = json.loads(args.manifest.read_text())

    before = json.dumps(docs, sort_keys=True)
    summary = patch_docs_nav(docs, manifest)
    after = json.dumps(docs, sort_keys=True)
    changed = before != after

    unique_removed = sorted(set(summary["removed"]))
    print(f"managed groups:        {summary['managed_groups']}")
    print(f"pages added to nav:    {len(summary['added'])}")
    print(f"pages removed from nav:{len(unique_removed)} "
          f"({len(summary['removed'])} occurrences across groups)")
    if unique_removed:
        for p in unique_removed:
            print(f"  - {p}")
    if summary["uncategorized"]:
        print(f"WARNING: {len(summary['uncategorized'])} new pages had no "
              "classify rule and were NOT placed in nav:")
        for p in summary["uncategorized"]:
            print(f"  ? {p}")
        print("  → extend classify_new() in this script, or place "
              "manually in docs.json.")
    if summary["missing_from_nav"]:
        print(f"ERROR: {len(summary['missing_from_nav'])} manifest pages "
              "missing from nav after patch:")
        for p in summary["missing_from_nav"]:
            print(f"  ! {p}")
        return 2
    if summary["unexpected_in_nav"]:
        print(f"ERROR: {len(summary['unexpected_in_nav'])} pages in nav "
              "are neither in manifest nor preserved:")
        for p in summary["unexpected_in_nav"]:
            print(f"  ! {p}")
        return 2

    if args.check:
        return 1 if changed else 0

    if changed:
        args.docs_json.write_text(json.dumps(docs, indent=2) + "\n")
        print(f"wrote {args.docs_json}")
    else:
        print("no changes — docs.json already in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
