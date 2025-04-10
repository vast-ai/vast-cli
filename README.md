# Welcome to Vast.ai’s Documentation!

## Overview
This repository contains the open source command line interface for Vast.ai. This CLI replicates much of the functionality available in the Vast.ai website GUI by using the same underlying REST API. Most of the functionality is contained within the single script file `vast.py`, while additional features (such as PDF invoice generation) are provided by the supplementary script `vast_pdf.py`. 

Our Python SDK is maintained through a separate repository [vast-ai/vast-sdk](https://github.com/vast-ai/vast-sdk).

[![PyPI version](https://badge.fury.io/py/vastai.svg)](https://badge.fury.io/py/vastai)

## Table of Contents
1. [Quickstart](#quickstart)
2. [Usage](#usage)
3. [Install](#install)
4. [Commands](#commands)
5. [List of Commands and Associated Help Message](#list-of-commands-and-associated-help-message)
6. [Self-Test a Machine (Single Machine)](#self-test-a-machine-single-machine)
7. [Host Machine Testing with `vast_machine_tester.py`](#host-machine-testing-with-vast_machine_testerpy)
8. [Usage Examples](#usage-examples)
9. [Tab-Completion](#tab-completion)

## Quickstart
It is recommended that you create a dedicated subdirectory to store this script and its related files. For example, you might create a directory named `vid` (short for "Vast Install Directory"):
```bash
mkdir vid
cd vid
```
Once inside your directory, download the `vast.py` script:
```bash
wget https://raw.githubusercontent.com/vast-ai/vast-python/master/vast.py
chmod +x vast.py
```
Verify that the script is working by running:
```bash
./vast.py --help
```
You should see a list of available commands. Next, log in to the Vast.ai website and obtain your API key from [https://vast.ai/console/cli/](https://vast.ai/console/cli/). Copy the provided command under "Login / Set API Key" and run it. The command will look similar to:
```bash
./vast.py set api-key xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
This command saves your API key in a hidden file in your home directory. **Keep your API key secure.**

You can test a search command with:
```bash
./vast.py search offers --limit 3
```
This should display a short list of machine offers.

We also now support Poetry as our dependency manager! If you're having trouble installing external packages, through `requirements.txt`, we recommend to use Poetry which manages this all for you.
In order to get started -

```bash
# Install poetry if you don't have it already.
curl -sSL https://install.python-poetry.org | python3 -
# Install project dependencies
poetry install
# Run vast.py
python vast.py

```
## Usage
The Vast.ai CLI provides a variety of commands for interacting with the Vast.ai platform. For example, you can search for available machines by running:
```bash
./vast.py search offers
```
To refine your search, consult the extensive help by running:
```bash
./vast.py search offers --help
```
You can filter results based on numerous parameters, similar to the website GUI.

For example, to find Turing GPU instances (with compute capability 7.0 or higher):
```bash
./vast.py search offers 'compute_cap > 700'
```
Or to find instances with a reliability score ≥ 0.99 and at least 4 GPUs (ordered by GPU count descending):
```bash
./vast.py search offers 'reliability > 0.99 num_gpus>=4' -o 'num_gpus-'
```

## Install
If you followed the [Quickstart](#quickstart) instructions, you have already installed the main CLI script (`vast.py`).  
For generating PDF invoices, you will need the `vast_pdf.py` script (found in this repository) and the third-party library [Borb](https://github.com/jorisschellekens/borb). To install Borb, run:
```bash
pip3 install borb
```

## Commands
The Vast.ai CLI is primarily contained within the `vast.py` script. Commands follow a simple "verb-object" pattern. For example, to run the command "show machines", you would type:
```bash
./vast.py show machines
```

## List of Commands and Associated Help Message
For a full list of commands and help messages, run:
```bash
./vast.py --help
```
This will display available commands including, but not limited to:
- `help`
- `create instance`
- `destroy instance`
- `search offers`
- `self-test machine`
- `show instances`
... and many others.

## Self-Test a Machine (Single Machine)
Hosts can perform a **self-test** on a single machine to verify that it meets the necessary requirements and passes reliability and stress tests.

### Usage
```bash
./vast.py self-test machine <machine_id> [--ignore-requirements]
```
- **`machine_id`**: The numeric ID of the machine to test.
- **`--ignore-requirements`** (optional): Continues tests even if system requirements are not met. If omitted, the self-test stops at the first requirement failure.

**Examples:**
```bash
# Standard self-test, respecting requirements:
./vast.py self-test machine 12345

# Self-test ignoring system requirements:
./vast.py self-test machine 12345 --ignore-requirements
```

**Output:**
1. **Requirements Check:**  
   The script verifies whether the machine meets all necessary requirements. If any requirements are not met, it will report the failures.
2. **Instance Creation:**  
   A temporary test instance is launched.
3. **Test Execution:**  
   A series of tests are performed (system checks, GPU tests, stress tests, etc.).
4. **Summary:**  
   The results are displayed, indicating whether the machine passed or failed along with any error messages.

The temporary test instance is automatically destroyed after testing.

## Host Machine Testing with `vast_machine_tester.py`
For hosts who want to automatically test multiple machines, the `vast_machine_tester.py` script is provided. This script:

1. **Searches** for offers based on host (`--host_id`) and verification status (`--verified`).
2. **Selects** the best offer for each machine (based on the highest `dlperf`).
3. **Optionally** samples a percentage of the machines (using `--sample-pct`).
4. **Performs** concurrent self-tests on the selected machines.
5. **Saves** results to:
   - `passed_machines.txt`
   - `failed_machines.txt`
6. **Outputs** a summary, including a table of failure reasons.

### Usage
```bash
python3 vast_machine_tester.py [--verified {true,false,any}] [--host_id HOST_ID] [--ignore-requirements] [--sample-pct SAMPLE_PCT] [-v | -vv | -vvv]
```

- **`--verified {true,false,any}`**  
  Which verification status to filter offers by (defaults to `false`).

- **`--host_id HOST_ID`**  
  Filter offers by a specific host ID (defaults to `any`).

- **`--ignore-requirements`**  
  Skip strict requirement checks; log them but proceed with the tests.

- **`--auto-verify {true,false}`**  
  - If `"true"`, any machine that passes is automatically set to `"verified"`.  
  - If `"false"` (or omitted), you are prompted whether to verify each passing machine.  

- **`--auto-deverify {true,false}`**  
  - If `"true"`, any failing machine is automatically set to `"deverified"`, with the failure reason stored in `error_msg`.  
  - If `"false"` (or omitted), you are prompted whether to deverify each failing machine.

- **`--sample-pct PCT`**  
  - Randomly test only PCT% of the machines that would otherwise be tested. E.g., `--sample-pct 30` tests ~30% of them.  
  - Default is `100`, meaning test all.

- **`-v | -vv | -vvv`**  
  - Increase verbosity level (INFO/DEBUG). By default logs are at WARNING level.

### Examples

1. **Test all unverified machines** for a specific Host ID (default `verified=false`):  
   ```
   python3 vast_machine_tester.py --host_id 123456
   ```
   Saves results to `passed_machines.txt` and `failed_machines.txt`.

2. **Test *any* machines** (verified or unverified):  
   ```
   python3 vast_machine_tester.py --verified any --host_id 123456
   ```

3. **Ignore system requirements**:  
   ```
   python3 vast_machine_tester.py --host_id 123456 --ignore-requirements
   ```

4. **Automatically verify** machines that pass:  
   ```
   python3 vast_machine_tester.py --host_id 123456 --auto-verify true
   ```

5. **Automatically deverify** failing machines:  
   ```
   python3 vast_machine_tester.py --host_id 123456 --auto-deverify true
   ```

6. **Only test 30%** of your machines:  
   ```
   python3 vast_machine_tester.py --host_id 123456 --sample-pct 30
   ```

### Output Files

- **`passed_machines.txt`**  
  Contains a timestamp and a **comma-separated** list of machine IDs that have passed.

- **`failed_machines.txt`**  
  Contains a timestamp and lines of the form `<machine_id>: <reason>` for each failure.

### Failure Summary
A short table is printed at the end, summarizing each unique failure reason (e.g., “No response for 60 seconds with running instance”).

## Usage Examples

### Single Machine Self-Test
```bash
./vast.py self-test machine 54321
```
If the machine fails to meet requirements, the output will indicate the failure reasons and the test will stop.

### Self-Test with Ignored Requirements
```bash
./vast.py self-test machine 54321 --ignore-requirements
```
This command will display the failing requirements but continue with the self-test.

### Testing Multiple Machines Automatically
```bash
python3 vast_machine_tester.py --host_id 123456 --ignore-requirements
```
This command will run self-tests on multiple machines from the specified host and output the results to `passed_machines.txt` and `failed_machines.txt`.

### Testing a Sample of Machines
```bash
python3 vast_machine_tester.py --host_id 123456 --sample-pct 30
```
This command tests approximately 30% of the machines, randomly sampled from the total list.

## Tab-Completion
The `vast.py` script supports tab-completion in both Bash and Zsh shells if the [argcomplete](https://github.com/kislyuk/argcomplete) package is installed. To enable tab-completion:

1. Install `argcomplete`:
   ```bash
   pip3 install argcomplete
   ```
2. Enable global tab-completion by running:
   ```bash
   activate-global-python-argcomplete
   ```
   Alternatively, for a single session, run:
   ```bash
   eval "$(register-python-argcomplete vast.py)"
   ```
   
*Note:* Rapid invocations via tab-completion might trigger API rate limits. If you experience issues, please report them in the project's GitHub issues.

---

This documentation should help you get started with the Vast.ai CLI tools and understand the available commands and usage patterns. For more detailed information, refer to the inline help provided by each command.
```
