#!/usr/bin/env python3
"""
ssh_diagnose.py — Diagnose why SSH into a Vast.ai instance is failing.

Usage:
    python3 ssh_diagnose.py <machine_id> <instance_id>
    python3 ssh_diagnose.py <machine_id> <instance_id> --api-key YOUR_KEY

API key is read from ~/.config/vastai/vast_api_key or ~/.vast_api_key if not passed.
"""

import argparse
import json
import os
import socket
import sys
import time

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL   = os.getenv("VAST_URL", "https://console.vast.ai")
APIKEY_FILE = os.path.expanduser("~/.config/vastai/vast_api_key")
APIKEY_LEGACY = os.path.expanduser("~/.vast_api_key")

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"  {GREEN}✔{RESET}  {msg}")
def warn(msg):  print(f"  {YELLOW}⚠{RESET}  {msg}")
def fail(msg):  print(f"  {RED}✘{RESET}  {msg}")
def info(msg):  print(f"  {CYAN}→{RESET}  {msg}")
def section(title): print(f"\n{BOLD}{title}{RESET}\n{'─'*50}")

# ── API helpers ────────────────────────────────────────────────────────────────
def api_get(path, api_key, params=None):
    params = params or {}
    params["api_key"] = api_key
    r = requests.get(f"{BASE_URL}/api/v0{path}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def load_api_key(provided):
    if provided:
        return provided
    for f in [APIKEY_FILE, APIKEY_LEGACY]:
        if os.path.exists(f):
            return open(f).read().strip()
    print(f"{RED}No API key found. Pass --api-key or set it via 'vastai set api-key YOUR_KEY'.{RESET}")
    sys.exit(1)

# ── Checks ─────────────────────────────────────────────────────────────────────
def check_port_open(host, port, timeout=5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def diagnose(machine_id, instance_id, api_key):
    issues   = []   # (description, solvable: bool, fix: str)
    results  = {}

    # ── 1. Fetch instance info ─────────────────────────────────────────────────
    section("1. Instance status")
    try:
        inst = api_get(f"/instances/{instance_id}/", api_key, {"owner": "me"})["instances"]
        results["instance"] = inst
    except Exception as e:
        fail(f"Could not fetch instance {instance_id}: {e}")
        issues.append(("Instance not found or not owned by this account", False,
                        "Verify the instance ID and that you're using the correct API key."))
        return issues

    actual_status   = inst.get("actual_status",  "unknown")
    intended_status = inst.get("intended_status", "unknown")
    status_msg      = inst.get("status_msg", "") or ""
    image_runtype   = inst.get("image_runtype",  "") or ""
    ssh_host        = inst.get("ssh_host")
    ssh_port        = inst.get("ssh_port")
    public_ipaddr   = inst.get("public_ipaddr")
    ports           = inst.get("ports") or {}
    inst_machine_id = inst.get("machine_id")

    info(f"actual_status:   {actual_status}")
    info(f"intended_status: {intended_status}")
    info(f"image_runtype:   {image_runtype}")
    info(f"status_msg:      {status_msg or '(none)'}")
    info(f"public_ip:       {public_ipaddr}")
    info(f"ssh_host:        {ssh_host}  ssh_port: {ssh_port}")
    info(f"ports:           {json.dumps(ports)}")

    if inst_machine_id and str(inst_machine_id) != str(machine_id):
        warn(f"Instance {instance_id} belongs to machine {inst_machine_id}, not {machine_id}.")

    # ── 2. Instance state ──────────────────────────────────────────────────────
    section("2. Instance state")
    if actual_status == "running":
        ok("Instance is running.")
    elif actual_status == "loading":
        warn("Instance is still loading — SSH daemon may not be ready yet.")
        issues.append(("Instance still loading", True, "Wait 30–60 seconds and retry SSH."))
    elif actual_status == "offline":
        fail("Instance is offline — the host machine has disconnected.")
        issues.append(("Instance offline", False,
                        "The host went offline. Destroy and rent a different machine."))
    elif actual_status in ("exited", "destroyed"):
        fail(f"Instance is {actual_status} — it is no longer running.")
        issues.append((f"Instance {actual_status}", False,
                        "Create a new instance on this or another machine."))
    else:
        warn(f"Unexpected status: '{actual_status}'.")

    if status_msg and "error" in status_msg.lower():
        fail(f"status_msg contains error: {status_msg}")
        issues.append(("Container error reported in status_msg", False, status_msg))

    # ── 3. SSH enabled in runtype ──────────────────────────────────────────────
    section("3. SSH runtype check")
    if "ssh" in image_runtype:
        ok(f"SSH is enabled in runtype: '{image_runtype}'")
    elif image_runtype == "args":
        fail("Instance launched in 'args' mode — SSH is NOT injected into this container type.")
        issues.append(("SSH not enabled (args runtype)", False,
                        "Recreate the instance without --args/--entrypoint, or use --ssh flag.\n"
                        "        args/entrypoint mode does not support SSH."))
    elif "jupyter" in image_runtype and "ssh" not in image_runtype:
        fail(f"Instance is jupyter-only ('{image_runtype}') — SSH is not enabled.")
        issues.append(("SSH not enabled (jupyter-only runtype)", True,
                        f"Attach SSH: vastai attach ssh {instance_id} $(cat ~/.ssh/id_rsa.pub)\n"
                        f"        Or recreate with both --jupyter and --ssh flags."))
    else:
        warn(f"Unrecognised runtype '{image_runtype}' — SSH may not be available.")

    # ── 4. SSH key check ───────────────────────────────────────────────────────
    section("4. SSH key")
    try:
        user_info = api_get("/users/current/", api_key)
        account_key = (user_info.get("ssh_key") or "").strip()
        if account_key:
            ok(f"SSH key registered on account: {account_key[:40]}...")
        else:
            fail("No SSH public key registered on this Vast account.")
            issues.append(("No SSH key on account", True,
                            "Run: vastai set ssh-key ~/.ssh/id_rsa.pub\n"
                            "        Or attach directly: vastai attach ssh "
                            f"{instance_id} $(cat ~/.ssh/id_rsa.pub)"))
    except Exception as e:
        warn(f"Could not fetch user info to verify SSH key: {e}")

    # ── 5. Port resolution ─────────────────────────────────────────────────────
    section("5. SSH port resolution")
    port_22_direct = ports.get("22/tcp")
    if port_22_direct:
        ssh_connect_host = public_ipaddr
        ssh_connect_port = int(port_22_direct[0]["HostPort"])
        ok(f"Direct port mapping found: {ssh_connect_host}:{ssh_connect_port}")
    elif ssh_host and ssh_port:
        # Jupyter offset: ssh_port+1 when jupyter in runtype
        offset = 1 if "jupyter" in image_runtype else 0
        ssh_connect_host = ssh_host
        ssh_connect_port = int(ssh_port) + offset
        if offset:
            warn(f"Jupyter runtype detected — SSH port is ssh_port+1: {ssh_connect_host}:{ssh_connect_port}")
        else:
            ok(f"SSH via proxy: {ssh_connect_host}:{ssh_connect_port}")
    else:
        fail("Cannot determine SSH host/port — no direct port mapping and no ssh_host/ssh_port.")
        issues.append(("SSH host/port not available", False,
                        "The machine may not have direct ports configured. "
                        "Check direct_port_count for this machine."))
        ssh_connect_host = None
        ssh_connect_port = None

    info(f"Use: ssh -p {ssh_connect_port} root@{ssh_connect_host}")

    # ── 6. Network connectivity ────────────────────────────────────────────────
    section("6. Network connectivity")
    if ssh_connect_host and ssh_connect_port:
        info(f"Testing TCP connection to {ssh_connect_host}:{ssh_connect_port}...")
        reachable = check_port_open(ssh_connect_host, ssh_connect_port)
        if reachable:
            ok(f"Port {ssh_connect_port} is open and reachable.")
        else:
            fail(f"Port {ssh_connect_port} is NOT reachable on {ssh_connect_host}.")
            issues.append((f"SSH port {ssh_connect_port} unreachable", False,
                            "Possible causes:\n"
                            "        - Host firewall blocking the port\n"
                            "        - Instance not yet fully started\n"
                            f"        - Machine went offline\n"
                            f"        Check: vastai search offers 'machine_id={machine_id} rentable=any verified=any'"))

    # ── 7. Machine offer status ────────────────────────────────────────────────
    section("7. Machine offer / online status")
    try:
        resp = api_get("/bundles/", api_key, {
            "q": json.dumps({
                "machine_id": {"eq": int(machine_id)},
                "verified":   {"eq": "any"},
                "rentable":   {"eq": "any"},
                "rented":     {"eq": "any"},
            })
        })
        offers = resp.get("offers", [])
        if offers:
            o = offers[0]
            info(f"Machine offer found — rentable: {o.get('rentable')}  rented: {o.get('rented')}  online: {o.get('machine_online')}")
            if not o.get("machine_online"):
                fail("Machine is showing as offline in offers.")
                issues.append(("Machine offline in marketplace", False,
                                "The host machine has gone offline. Your instance may be lost."))
            else:
                ok("Machine is online in the marketplace.")
        else:
            warn("No offer found for this machine — it may have been delisted or is fully rented.")
    except Exception as e:
        warn(f"Could not fetch machine offer: {e}")

    return issues

# ── Summary ────────────────────────────────────────────────────────────────────
def print_summary(issues):
    section("Summary")
    if not issues:
        ok("No issues detected. If SSH still fails, verify your local SSH key matches the one registered on your account.")
        info("Try: vastai ssh-url <instance_id>  — to get the exact SSH command.")
        return

    solvable   = [i for i in issues if i[1]]
    unsolvable = [i for i in issues if not i[1]]

    if solvable:
        print(f"\n{YELLOW}{BOLD}Fixable issues:{RESET}")
        for desc, _, fix in solvable:
            print(f"  {YELLOW}⚠{RESET} {desc}")
            print(f"     Fix: {fix}\n")

    if unsolvable:
        print(f"\n{RED}{BOLD}Issues that require a new instance:{RESET}")
        for desc, _, fix in unsolvable:
            print(f"  {RED}✘{RESET} {desc}")
            print(f"     {fix}\n")

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Diagnose SSH failures for a Vast.ai instance.")
    parser.add_argument("machine_id",  type=int, help="Machine ID")
    parser.add_argument("instance_id", type=int, help="Instance ID")
    parser.add_argument("--api-key",   type=str, default=None, help="Vast.ai API key")
    args = parser.parse_args()

    api_key = load_api_key(args.api_key)

    print(f"\n{BOLD}SSH Diagnostics — machine {args.machine_id}, instance {args.instance_id}{RESET}")
    print(f"{'═'*50}")

    issues = diagnose(args.machine_id, args.instance_id, api_key)
    print_summary(issues)

if __name__ == "__main__":
    main()
