#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
# =============================================================================
# Script Name: vast_machine_tester.py
# Description:
#     This Python script automates the process of searching for offers using the
#     VAST tool, filtering offers based on the --verification and --host_id flags,
#     selecting the best offers (highest dlperf) for each machine, performing
#     self-tests on each machine, and saving the test results.
#
# Execution:
#     Ensure that all dependencies are installed and that the './vast' or
#     './vast.py' commands are available and executable. Run the script using:
#         python3 vast_machine_tester.py [--verification {verified,unverified,deverified,any}]
#                                        [--host_id HOST_ID]
#                                        [--ignore-requirements]
#                                        [--sample-pct SAMPLE_PCT]
#                                        [-v | -vv | -vvv]
#
#     Examples:
#         python3 vast_machine_tester.py --verification verified --ignore-requirements
#         python3 vast_machine_tester.py --verification unverified --host_id 12345
#         python3 vast_machine_tester.py --verification any --sample-pct 30
#
# Results:
#     - Passed machine IDs are saved to 'passed_machines.txt'
#     - Failed machine IDs and reasons are saved to 'failed_machines.txt'
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

# -----------------------------
#   USE SAME PATHS AND LOGIC AS vast.py FOR STORING/READING API KEY
# -----------------------------
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


# -----------------------------
#   MAIN SCRIPT FUNCTIONS
# -----------------------------

def setup_logging(verbosity: int):
    """
    Configures the logging settings based on the verbosity level.
      0 => WARNING
      1 => INFO
      2 => DEBUG
      3 => also DEBUG
    """
    if verbosity >= 3:
        level = logging.DEBUG
    elif verbosity == 2:
        level = logging.DEBUG
    elif verbosity == 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
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


def run_vast_search(host_id='any', ignore_requirements=False):
    """
    Executes the VAST search command to retrieve *all* offers, regardless of 
    'verified' status, so that local filtering can handle it. If 'ignore_requirements'
    is false, reliability > 0.9 is included in the query. Otherwise it's omitted.
    Includes up to 30 retries if we get a 429 Too Many Requests error.
    """

    # We won't use the user-supplied 'verified' for the search 
    # but we do preserve the user-supplied 'host_id'
    if host_id != 'any':
        try:
            int(host_id)
        except ValueError:
            logging.error(f"Invalid value for --host_id: '{host_id}'. Must be an integer or 'any'.")
            sys.exit(1)

    # Force 'verified=any' in the actual search, so we get all machines
    verified_filter = "verified=any"

    # Construct the host filter
    host_id_filter = f"host_id={host_id}" if host_id != 'any' else "host_id=any"

    # Build the command
    if not ignore_requirements:
        cmd = [
            get_vast_command(), 'search', 'offers', '--limit', '65535',
            '--disable-bundling', 'reliability > 0.9',
            verified_filter, host_id_filter, '--raw'
        ]
    else:
        cmd = [
            get_vast_command(), 'search', 'offers', '--limit', '65535',
            '--disable-bundling',
            verified_filter, host_id_filter, '--raw'
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
            all_output_lower = (result.stdout + result.stderr).lower()
            if "429" in all_output_lower or "too many requests" in all_output_lower:
                if attempt < max_retries:
                    wait_time = random.randint(2, 20)
                    logging.warning(
                        f"429 in JSON decode for run_vast_search. Retrying in {wait_time}s... "
                        f"(Attempt {attempt}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logging.error("Too Many Requests (JSON decode) after max retries.")
                    return []
            else:
                logging.error(f"Error parsing JSON output from vast search: {e}")
                return []

        except Exception as e:
            logging.exception(f"Unexpected error running vast search: {e}")
            return []

    logging.error("Exhausted all retries in run_vast_search without success.")
    return []


def get_filtered_offers(offers, verification_status):
    """
    Filters the list of offers to remove any that are 'verified'.
    """
    return [off for off in offers if off.get('verification') != verification_status]


def get_best_offers(offers):
    """
    Selects the best offer for each machine based on highest dlperf.
    Returns a dict machine_id -> best offer.
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
    Up to 30 retries if "429" or "Too Many Requests".
    Returns: (machine_id, status, reason)
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

            # Parse JSON
            try:
                data = json.loads(output)
            except json.JSONDecodeError:
                # Could still be leftover 429 message
                if "429" in all_output_lower or "too many requests" in all_output_lower:
                    if attempt < max_retries:
                        wait_time = random.randint(2, 20)
                        logging.warning(f"429 in JSON output for machine {machine_id}. Retrying...")
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
    Concurrent execution of self-tests on multiple machines.
    Returns (successes, failures).
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
                    f"Processed {processed}/{total_machines} - Passed: {passed}, "
                    f"Failed: {failed}, Remaining: {remaining}"
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
        logging.info("Saved failed_machines to 'failed_machines.txt'.")
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
    python3 vast_machine_tester.py --verification verified --host_id any --ignore-requirements
    python3 vast_machine_tester.py --verification unverified any -vv

Results are saved to 'passed_machines.txt' and 'failed_machines.txt'.
        """
    )
    parser.add_argument(
        '--verification',
        type=str,
        choices=['unverified', 'verified', 'deverified', 'any'],
        default='false',
        help="Which verification status to filter offers by: 'unverifed', 'verified', 'deverified', 'any'. (Default: 'unverified')"
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
        help="Ignore the minimum system requirements in 'self-test machine' and do NOT filter by 'reliability > 0.9'."
    )
    parser.add_argument(
        '--sample-pct',
        type=float,
        default=100.0,
        help="Randomly sample only this percentage of machines to test. E.g., '30' means test ~30%% of them. Default = 100."
    )
    parser.add_argument(
        '-v', '--verbose',
        action='count',
        default=0,
        help="Increase logging verbosity (use -v, -vv, -vvv)"
    )

    return parser.parse_args()


def main():
    args = parse_arguments()
    setup_logging(args.verbose)

    offers = run_vast_search(
        host_id=args.host_id,
        ignore_requirements=args.ignore_requirements
    )
    if not offers:
        logging.error("No offers found or an error occurred during the VAST search.")
        return

    # If user specifically wants 'false' (unverified), filter out machines that might be partially verified
    if args.verification == 'any':
        offers_to_process = offers
    else:
        filtered_offers = get_filtered_offers(offers, args.verification)
        offers_to_process = filtered_offers
        logging.info(f"Filtered to {len(filtered_offers)} {args.verification} offer(s).")

    best_offers = get_best_offers(offers_to_process)
    machine_ids = list(best_offers.keys())
    logging.info(f"Found {len(machine_ids)} machine ID(s) to test.")

    # -----------------------------------------------------------
    #   RANDOMLY SAMPLE X% OF THEM
    #   e.g. if user used --sample-pct=30 => test only ~30%
    # -----------------------------------------------------------
    if args.sample_pct < 100.0:
        if args.sample_pct <= 0:
            logging.warning("--sample-pct <= 0 means 0% => skipping all tests.")
            machine_ids = []
        else:
            random.shuffle(machine_ids)
            sample_count = int(len(machine_ids) * (args.sample_pct / 100.0))
            machine_ids = machine_ids[:sample_count]
            logging.info(
                f"Randomly sampling {args.sample_pct}% => {sample_count} machine(s) out of total."
            )

    if not machine_ids:
        logging.warning("No machines to test after sampling.")
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


if __name__ == '__main__':
    main()
