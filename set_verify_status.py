#!/usr/bin/env python3
import sys
import os
import requests
import json

def main():
    if len(sys.argv) < 3:
        print("Usage: set_verify_status.py <machine_id> <verification_status>")
        print("Example: set_verify_status.py 29309 verified")
        sys.exit(1)

    machine_id = sys.argv[1]
    verification_status = sys.argv[2]

    # Get your admin token from env variable (or hardcode for testing)
    # For example, if you have `export ADMIN_TOKEN="eyJhbGciOiJIUzI1NiIsInR..."`
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        print("ERROR: ADMIN_TOKEN environment variable not set.")
        sys.exit(1)

    # The payload to match your admin_set_machines_verification_status endpoint
    payload = {
        "machine_ids": [int(machine_id)],
        "verification": verification_status
    }

    # Adjust the URL to your deployment or dev server:
    url = "https://cloud.vast.ai/api/admin/set_machines_verification_status"

    headers = {
        "Content-Type": "application/json",
        # For example, if you do Bearer tokens:
        "Authorization": f"Bearer {admin_token}"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print("Response content:", response.text)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
        sys.exit(1)

    # If we got here, the request succeeded (2xx)
    resp_json = response.json()
    if "success" in resp_json and resp_json["success"] == True:
        print(f"Success: Machine {machine_id} set to {verification_status}")
    else:
        print("Response from server:", resp_json)

if __name__ == "__main__":
    main()
