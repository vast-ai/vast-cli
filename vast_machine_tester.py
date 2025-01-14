#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
# =============================================================================
# Script Name: vast_machine_tester.py
# Description:
#     This Python script automates the process of searching for offers using the
#     VAST tool, filtering offers based on the --verified and --host_id flags,
#     selecting the best offers (highest dlperf) for each machine, performing
#     self-tests on each machine, and saving the test results. When done, it
#     optionally allows you to verify all machines that passed the self-test by
#     calling the Vast admin endpoint.
#
# Execution:
#     Ensure that all dependencies are installed and that the './vast' or
#     './vast.py' commands are available and executable. Run the script using:
#         python3 vast_machine_tester.py [--verified {true,false,any}] [--host_id HOST_ID]
#                                        [--ignore-requirements] [--auto-verify <true|false>]
#
#     Examples:
#         python3 vast_machine_tester.py --verified false --ignore-requirements
#         python3 vast_machine_tester.py --verified false --host_id 12345 --auto-verify true
#
# Results:
#     - Passed machine IDs are saved to 'passed_machines.txt'
#     - Failed machine IDs and reasons are saved to 'failed_machines.txt'
#     - Optionally, user is prompted or (if auto-verify is true) automatically
#       verifies all machines that passed self-tests.
# =============================================================================

import subprocess
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime
import time
import random
from collections import Counter
import argparse
import sys
import os
import logging
import shutil
import requests

try:
    from tabulate import tabulate
except ImportError:
    tabulate = None
    logging.warning("Tabulate module not found. Table formatting will be basic.")


# -----------------------------------------------------------------------------
#   USE SAME PATHS AND LOGIC AS vast.py FOR STORING/READING API KEY
# -----------------------------------------------------------------------------

DIRS = {
    'config': os.path.join(os.path.expanduser('~'), '.config', 'vastai'),
    'temp': os.path.join(os.path.expanduser('~'), '.cache', 'vastai'),
}
for key, path in DIRS.items():
    if not os.path.exists(path):
        os.makedirs(path)

APIKEY_FILE = os.path.join(DIRS['config'], "vast_api_key")
APIKEY_FILE_HOME = os.path.expanduser("~/.vast_api_key")

if os.path.exists(APIKEY_FILE_HOME) and not os.path.exists(APIKEY_FILE):
    try:
        shutil.copyfile(APIKEY_FILE_HOME, APIKEY_FILE)
    except Exception as e:
        logging.error(f"Failed to copy legacy API key from {APIKEY_FILE_HOME} to {APIKEY_FILE}: {e}")


def load_api_key():
    """
    Reads the user's API key from the same config file that vast.py uses:
    ~/.config/vastai/vast_api_key
    """
    if not os.path.exists(APIKEY_FILE):
        return None
    try:
        with open(APIKEY_FILE, "r") as f:
            return f.read().strip()
    except Exception as e:
        logging.error(f"Unable to read API key from {APIKEY_FILE}: {e}")
        return None


# -----------------------------------------------------------------------------
#   MAIN SCRIPT FUNCTIONS
# -----------------------------------------------------------------------------

def setup_logging():
    """
    Configures the logging settings.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def get_vast_command():
    """
    Determines whether './vast.py' or './vast' is available as the executable command.
    """
    if os.path.isfile('./vast.py') and os.access('./vast.py', os.X_OK):
        logging.debug("Using './vast.py' as the VAST command.")
        return './vast.py'
    elif os.path.isfile('./vast') and os.access('./vast', os.X_OK):
        logging.debug("Using './vast' as the VAST command.")
        return './vast'
    else:
        logging.error("Neither './vast.py' nor './vast' is available as an executable.")
        raise FileNotFoundError("Neither './vast.py' nor './vast' is available as an executable.")


def run_vast_search(verified='any', host_id='any'):
    """
    Executes the VAST search command to retrieve offers based on verification status and host ID.
    Implements up to 30 retries if we get a 429 Too Many Requests error.

    Parameters:
        verified (str): 'true', 'false', or 'any' to filter offers by verification status.
        host_id (str or int): Specific host ID to filter offers or 'any' for no filtering.

    Returns:
        list of dict: A list of offer dictionaries.
    """
    valid_verified = {'true', 'false', 'any'}
    if verified.lower() not in valid_verified:
        logging.error(f"Invalid value for --verified: '{verified}'. Must be one of {valid_verified}.")
        sys.exit(1)
    
    if host_id != 'any':
        try:
            int(host_id)
        except ValueError:
            logging.error(f"Invalid value for --host_id: '{host_id}'. Must be an integer or 'any'.")
            sys.exit(1)
    
    verified_filter = f"verified={verified.lower()}"
    host_id_filter = f"host_id={host_id}" if host_id != 'any' else "host_id=any"

    cmd = [
        get_vast_command(), 'search', 'offers', '--limit', '65535',
        '--disable-bundling', verified_filter, host_id_filter, '--raw'
    ]

    max_retries = 30
    for attempt in range(1, max_retries + 1):
        try:
            logging.info(f"Running VAST search (attempt {attempt}) with command: {' '.join(cmd)}")
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            output = result.stdout
            offers = json.loads(output)
            logging.info(f"Retrieved {len(offers)} offers from VAST search.")
            return offers

        except subprocess.CalledProcessError as e:
            # If we see a 429 or "Too Many Requests", do backoff
            stderr_msg = e.stderr.strip().lower()
            if "429" in stderr_msg or "too many requests" in stderr_msg:
                if attempt < max_retries:
                    wait_time = random.randint(2, 20)
                    logging.warning(
                        f"429 Too Many Requests while searching offers. "
                        f"Retrying in {wait_time}s... (Attempt {attempt}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logging.error("Too Many Requests error after max retries in run_vast_search.")
                    return []
            else:
                logging.error(f"Error running vast search: {e.stderr.strip()}")
                return []

        except json.JSONDecodeError as e:
            # Could still be a 429 in the output
            # We'll check the partial output
            if "429" in str(e) or "too many requests" in (result.stdout.lower() + result.stderr.lower()):
                if attempt < max_retries:
                    wait_time = random.randint(2, 20)
                    logging.warning(
                        f"429 in JSON decode for run_vast_search. Retrying in {wait_time}s... "
                        f"(Attempt {attempt}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logging.error("Too Many Requests (JSON decode) after max retries in run_vast_search.")
                    return []
            else:
                logging.error(f"Error parsing JSON output from vast search: {e}")
                return []

        except Exception as e:
            logging.exception(f"Unexpected error running vast search: {e}")
            return []

    # If we somehow exhaust all attempts without returning
    logging.error("Exhausted all retries in run_vast_search without success.")
    return []


def get_unverified_offers(offers):
    """
    Filters the list of offers to only unverified offers whose machine IDs are not
    present in any verified offers.
    """
    verified_machine_ids = {
        off.get('machine_id') for off in offers if off.get('verification') == 'verified'
    }

    unverified_offers = [
        off for off in offers
        if off.get('verification') == 'unverified'
           and off.get('machine_id') not in verified_machine_ids
    ]
    logging.info(f"Filtered to {len(unverified_offers)} truly unverified offers.")
    return unverified_offers


def get_best_offers(offers):
    """
    Selects the best offer for each machine based on the highest deep learning performance (dlperf).
    Returns a dict mapping machine_id -> best offer.
    """
    best_offers = {}
    for off in offers:
        machine_id = off.get('machine_id')
        dlperf = off.get('dlperf', 0)
        if machine_id not in best_offers or dlperf > best_offers[machine_id].get('dlperf', 0):
            best_offers[machine_id] = off
    logging.info(f"Selected best offers for {len(best_offers)} machines based on dlperf.")
    return best_offers


def test_machine(machine_id, ignore_requirements=False):
    """
    Performs a self-test on a given machine using 'vast self-test machine <id>'.
    Adds up to 30 retries if "429" or "Too Many Requests" is encountered.

    Returns: (machine_id, status, reason)
      status = 'success' or 'failure'
      reason = if failure, text reason
    """
    cmd = [get_vast_command(), 'self-test', 'machine', str(machine_id), '--raw']
    if ignore_requirements:
        cmd.append('--ignore-requirements')

    max_retries = 30
    for attempt in range(1, max_retries + 1):
        try:
            logging.debug(f"Testing machine {machine_id}, attempt {attempt}.")
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            output = result.stdout.strip()
            stderr_output = result.stderr.strip()

            # Check for rate-limiting or 429
            all_output_lower = (output + stderr_output).lower()
            if "429" in all_output_lower or "too many requests" in all_output_lower:
                if attempt < max_retries:
                    wait_time = random.randint(2, 20)
                    logging.warning(
                        f"429 Too Many Requests for machine {machine_id}. "
                        f"Retrying in {wait_time}s... (Attempt {attempt}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    return (machine_id, 'failure', "Too Many Requests after 30 retries")

            # Try to parse JSON
            try:
                data = json.loads(output)
            except json.JSONDecodeError:
                # Could still be a leftover 429 type error
                if "429" in all_output_lower or "too many requests" in all_output_lower:
                    if attempt < max_retries:
                        wait_time = random.randint(2, 20)
                        logging.warning(
                            f"429 in JSON output for machine {machine_id}. "
                            f"Retrying in {wait_time}s... (Attempt {attempt}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        return (machine_id, 'failure', "Too Many Requests after 30 retries (JSON decode)")
                else:
                    error_message = stderr_output or output
                    logging.error(f"Invalid JSON for machine {machine_id}: {error_message}")
                    return (machine_id, 'failure', f"Invalid JSON or error: {error_message}")

            if data.get('success'):
                logging.info(f"Machine {machine_id} passed the self-test.")
                return (machine_id, 'success', '')
            else:
                reason = data.get('reason', 'Unknown reason')
                logging.warning(f"Machine {machine_id} failed the self-test: {reason}")
                return (machine_id, 'failure', reason)

        except Exception as e:
            logging.exception(f"Exception while testing machine {machine_id}: {e}")
            return (machine_id, 'failure', f"Exception occurred: {e}")

    return (machine_id, 'failure', "Request failed after 30 retries")


def process_machine_ids(machine_ids, ignore_requirements=False):
    """
    Manages concurrent execution of self-tests on multiple machines.
    Returns (successes, failures), where:
      successes = list of machine_ids that passed
      failures = list of (machine_id, reason)
    """
    successes = []
    failures = []
    total_machines = len(machine_ids)
    counter = {'processed': 0, 'passed': 0, 'failed': 0}
    lock = threading.Lock()
    
    logging.info(f"Starting self-tests on {total_machines} machine(s)...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(test_machine, mid, ignore_requirements): mid for mid in machine_ids}
        for future in as_completed(futures):
            machine_id, status, reason = future.result()
            with lock:
                counter['processed'] += 1
                if status == 'success':
                    successes.append(machine_id)
                    counter['passed'] += 1
                else:
                    failures.append((machine_id, reason))
                    counter['failed'] += 1
                
                processed = counter['processed']
                passed = counter['passed']
                failed = counter['failed']
                remaining = total_machines - processed
                logging.info(
                    f"Processed {processed}/{total_machines} - Passed: {passed}, Failed: {failed}, Remaining: {remaining}"
                )
    return successes, failures


def save_results(successes, failures):
    """
    Saves test results to 'passed_machines.txt' and 'failed_machines.txt'.
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Save passed
    try:
        with open('passed_machines.txt', 'w') as f:
            f.write(f"{current_time}\n")
            f.write(','.join(str(mid) for mid in successes) + "\n")
        logging.info("Saved passed machines to 'passed_machines.txt'.")
    except Exception as e:
        logging.error(f"Error saving passed_machines.txt: {e}")
    
    # Save failed
    try:
        with open('failed_machines.txt', 'w') as f:
            f.write(f"{current_time}\n")
            for mid, reason in failures:
                f.write(f"{mid}: {reason}\n")
        logging.info("Saved failed machines to 'failed_machines.txt'.")
    except Exception as e:
        logging.error(f"Error saving failed_machines.txt: {e}")


def print_failure_summary(failures):
    """
    Prints summary table of failure reasons.
    """
    reasons = [reason for _, reason in failures]
    failure_counts = Counter(reasons)
    
    table_data = []
    for reason, count in failure_counts.items():
        table_data.append([count, reason])
    table_data.sort(key=lambda x: x[0], reverse=True)
    
    print("\nFailed Machines by Error Type:")
    if tabulate:
        print(tabulate(table_data, headers=["COUNT", "REASON"], tablefmt="plain"))
    else:
        print(f"{'COUNT':<5} {'REASON'}")
        print("-" * 60)
        for count, reason in table_data:
            print(f"{count:<5} {reason}")


def parse_arguments():
    """
    Parses command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Automate searching and testing of VAST offers.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""\
Example Usage:
    python3 vast_machine_tester.py --verified false --host_id any --ignore-requirements
    python3 vast_machine_tester.py --verified false --auto-verify true

Results are saved to 'passed_machines.txt' and 'failed_machines.txt'.
        """
    )
    parser.add_argument(
        '--verified',
        type=str,
        choices=['true', 'false', 'any'],
        default='false',
        help="Which verification status to filter offers by: 'true', 'false', 'any'. (Default: 'false')"
    )
    parser.add_argument(
        '--host_id',
        type=str,
        default='any',
        help="Specify a particular host ID to filter offers or 'any' for no filtering. (Default: 'any')"
    )
    parser.add_argument(
        '--ignore-requirements',
        action='store_true',
        help="Ignore the minimum system requirements in 'self-test machine'."
    )
    parser.add_argument(
        '--auto-verify',
        type=str,
        choices=['true', 'false'],
        default='false',
        help="If 'true', automatically verify all machines that pass the self-test. "
             "If 'false' or not provided, you will be prompted. (Default: 'false')"
    )
    return parser.parse_args()


def verify_machines(machine_ids):
    """
    Verifies a list of machine IDs by calling the admin endpoint:
      POST https://console.vast.ai/api/admin/set_machines_verification_status/
    Then checks the 'success' field in the JSON response and prints a confirmation.
    """
    api_key = load_api_key()
    if not api_key:
        logging.error("No API key found; cannot verify machines.")
        return

    url = "https://console.vast.ai/api/admin/set_machines_verification_status/"
    payload = {
        "machine_ids": machine_ids,
        "verification": "verified"
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        logging.info(f"Sending POST request to {url} to verify machines {machine_ids}")
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()  # Raise error if non-2xx
        result = resp.json()

        if result.get("success") is True:
            msg = f"Successfully verified machines: {machine_ids}"
            logging.info(msg)
            print(msg)
        else:
            # If 'success' is missing or False, log it.
            msg = f"Could NOT verify machines {machine_ids}. Server response:\n{result}"
            logging.error(msg)
            print(msg)

    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP Error verifying machines: {e}")
        print(f"HTTP Error verifying machines: {e}")
    except Exception as e:
        logging.error(f"Error verifying machines: {e}")
        print(f"Error verifying machines: {e}")


def prompt_verification(successes, auto_verify='false'):
    """
    If there are machines that passed, determines whether to verify them automatically
    (if --auto-verify true) or prompt the user (if false).
    """
    if not successes:
        return

    # If --auto-verify was set to 'true', skip prompt
    if auto_verify.lower() == 'true':
        verify_machines(successes)
        return

    # Otherwise, prompt
    print("\nThe following machines passed all self-tests:\n", successes)
    answer = input("Would you like to mark these machines as 'verified'? (y/n): ").strip().lower()
    if answer == 'y':
        verify_machines(successes)


def main():
    setup_logging()
    args = parse_arguments()
    
    offers = run_vast_search(verified=args.verified, host_id=args.host_id)
    if not offers:
        logging.error("No offers found or an error occurred during the VAST search.")
        return
    
    # If user wants 'false' (unverified), filter out machines partially verified
    if args.verified.lower() == 'false':
        unverified_offers = get_unverified_offers(offers)
        offers_to_process = unverified_offers
        logging.info(f"Filtered to {len(unverified_offers)} unverified offer(s).")
    else:
        offers_to_process = offers
        logging.info(f"Using all {len(offers)} offer(s).")
    
    best_offers = get_best_offers(offers_to_process)
    machine_ids = list(best_offers.keys())
    logging.info(f"Found {len(machine_ids)} machine ID(s) to self-test.")
    if not machine_ids:
        logging.warning("No machines to test.")
        return

    successes, failures = process_machine_ids(machine_ids, ignore_requirements=args.ignore_requirements)
    save_results(successes, failures)

    logging.info("\nSummary:")
    logging.info(f"Passed: {len(successes)}")
    logging.info(f"Failed: {len(failures)}")

    if failures:
        print_failure_summary(failures)
    else:
        logging.info("All machines passed the self-tests.")

    logging.info("Results saved to 'passed_machines.txt' and 'failed_machines.txt'.")

    # Attempt to verify passed machines based on user input or --auto-verify
    prompt_verification(successes, auto_verify=args.auto_verify)


if __name__ == '__main__':
    main()
