# Welcome to Vast.ai’s documentation!

## Overview
This repository contains the open source python command line interface for vast.ai.
This CLI has all of the main functionality of the vast.ai website GUI and uses the
same underlying REST API. Most of the functionality is self-contained in the single
script file `vast.py`, although the invoice generating commands
require installing an additional second script called `vast_pdf.py`.

[![PyPI version](https://badge.fury.io/py/vastai.svg)](https://badge.fury.io/py/vastai)

## Table of Contents
1. [Quickstart](#quickstart)
2. [Usage](#Usage)
3. [Install](#Install)
4. [Commands](#Commands)
5. [List of commands and associated help message](#List-of-commands-and-associated-help-message)
6. [Self-Test a Machine (Single Machine)](#self-test-a-machine-single-machine)
7. [Host Machine Testing with `vast_machine_tester.py`](#host-machine-testing-with-vast_machine_testerpy)
8. [Usage Examples](#usage-examples)
9. [Tab-Completion](#tab-completion)

## Quickstart

You should probably create a subdirectory in which to put this script and related files if you
haven't already. You can call it whatever you like but I'll refer to it as "vid" for "Vast Install Directory".
So just enter `mkdir vid` to create the directory. Once you've created the directory just change your working directory to it with `cd vid`. After you've
done that the quickest way to get started is to download the `vast.py` script using the `wget` command.

```wget https://raw.githubusercontent.com/vast-ai/vast-python/master/vast.py; chmod +x vast.py;```

You can verify that the script is working by doing `./vast.py --help`. You should see a list of the available
commands. In order to proceed further you will need to login to the vast.ai website and get your api-key.
Go to [https://vast.ai/console/cli/](https://vast.ai/console/cli/). Copy the command under 
the heading "Login / Set API Key" and run it. The command will be something like

```./vast.py set api-key xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx```

where the `xxxx...` is your api-key (a long hexadecimal number). Note that if the script is
named "vast" in this command on the website and your installed script is named "vast.py"
you will need to change the name of the script in the command you run. The `set api-key`
command saves your api-key in a hidden file in your home directory. Do not share your
api-key with anyone as it authenticates your other vast commands to your account.

Check you can run a search:

```./vast.py search offers --limit 3```
You should see a small list of machine offers in tabular format.

## Usage

To see how the API works you can use it to find machines for rent. `vast.py search offers`. In this
form the command will show all available offers. To get more specific results try narrowing the search.
There is a large online help page on how to do this. Bring up the help by doing `vast.py search offers --help`.
There are many parameters that can be used to filter the results. The search command supports
all of the filters and sort options that the website GUI uses. To find Turing GPU instances
(compute capability 7.0 or higher):

```./vast.py search offers 'compute_cap > 700 '```

To find instances with a reliability score >= 0.99 and at least 4 gpus, ordering by num of gpus
descending:

```./vast.py search offers 'reliability > 0.99  num_gpus>=4' -o 'num_gpus-'```

The output of this command at the time of this writing is
```
ID       CUDA  Num  Model        PCIE_BW  vCPUs     RAM  Storage  $/hr     DLPerf  DLP/$  Nvidia Driver Version  Net_up  Net_down  R      Max_Days  machine_id
1596177  11.4  10x  GTX_1080     5.5      48.0    257.9  4628     2.0000   73.0    36.5   470.63.01              653.3   854.5     99.5   -         638
2459430  11.5   8x  RTX_A5000    9.1      128.0   515.8  3094     4.0000   209.4   52.3   495.46                 1844.2  2669.6    99.7   12.0      4384
2459380  11.4   8x  RTX_3070     6.3      12.0     64.0  710      1.4200   67.2    47.3   470.86                 0.0     0.0       99.8   -         4102
2456624  11.4   8x  RTX_2080_Ti  10.7     32.0    257.9  1653     2.8000   126.4   45.2   470.82.00              14.6    214.2     99.8   28.7      3047
2456622  11.4   8x  RTX_2080_Ti  10.8     32.0    128.9  1651     2.8000   127.1   45.4   470.82.00              14.9    214.7     99.1   28.7      1569
2456600  11.5   8x  RTX_2080_Ti  10.9     48.0    256.6  1704     2.4000   125.5   52.3   495.29.05              169.0   169.8     99.7   25.7      4058
2455617  11.2   8x  RTX_3090     21.7     64.0    515.8  6165     6.4000   261.1   40.8   460.67                 477.6   707.2     99.8   28.7      2980
2454397  11.2   8x  A100_SXM4    22.4     128.0  2064.1  21568    13.2000  300.1   22.7   460.106.00             708.7   1119.8    99.2   -         4762
2405590  11.4   8x  RTX_2080_Ti  11.2     48.0    257.9  1629     3.8000   125.5   33.0   470.82.00              389.4   608.8     100.0  1.8       2776
2364579  11.4   8x  A100_PCIE    18.5     128.0   515.8  4813     14.8000  278.8   18.8   470.74                 472.4   699.0     99.9   28.7      3459
2281839  11.2   8x  Tesla_V100   11.8     72.0    483.1  1171     5.6000   193.6   34.6   460.67                 493.0   697.8     100.0  28.7      2744
2281832  11.2   8x  A100_PCIE    17.7     64.0    515.9  5821     14.8000  276.7   18.7   460.91.03              478.2   655.5     99.9   28.7      2901
2452630  11.4   7x  RTX_3090     6.3      28.0     64.0  61       3.5000   165.5   47.3   470.86                 84.6    84.4      99.3   3.8       4420
2342561  11.4   7x  RTX_3090     6.1      96.0    257.6  1664     4.5500   149.2   32.8   470.82.00              476.9   671.7     99.4   1.7       4202
2237983  11.4   7x  RTX_3090     12.5     32.0    257.6  3228     3.1500   204.5   64.9   470.86                 194.4   183.8     99.1   -         4207
2459511  11.4   6x  RTX_3090     6.2      -       128.8  812      2.8200   150.2   53.2   470.94                 374.4   271.4     99.0   6.7       3129
2448342  11.5   6x  RTX_A6000    12.4     64.0    515.7  6695     3.6000   169.8   47.2   495.29.05              668.6   1082.6    99.6   -         3624
2437565  11.4   6x  RTX_3090     23.0     16.0    128.8  1676     5.4000   196.8   36.5   470.94                 34.1    131.5     99.4   -         4238
2332973  11.2   6x  RTX_3090     11.9     48.0    193.3  1671     3.3000   180.3   54.6   460.84                 582.1   737.6     99.9   25.6      3552
2459459  11.5   4x  RTX_3090     23.1     32.0    257.8  1363     2.0000   131.2   65.6   495.46                 1954.7  2725.8    99.6   12.0      3059
2459428  11.5   4x  RTX_A5000    24.6     64.0    515.8  1547     2.0000   104.9   52.4   495.46                 1844.2  2669.6    99.7   12.0      4384
2459368  11.4   4x  RTX_3090     25.3     48.0     64.2  133      1.3967   130.5   93.4   470.86                 0.0     0.0       99.4   -         4637
2458968  11.6   4x  RTX_3090     11.7     16.0    128.5  752      1.4000   79.8    57.0   510.39.01              797.8   842.7     99.9   4.0       2555
2458878  11.6   4x  RTX_3090     11.6     36.0    128.5  1531     1.4000   81.9    58.5   510.39.01              757.1   807.6     99.9   4.0       3646
2458845  11.6   4x  RTX_3090     3.1      12.0    128.5  369      1.4000   92.4    66.0   510.39.01              725.7   852.2     99.8   4.0       700
2458838  11.6   4x  RTX_3090     5.7      48.0    128.9  624      1.4000   85.3    60.9   510.39.01              574.9   731.7     99.8   4.0       2217
2454395  11.2   4x  A100_SXM4    22.9     64.0   2064.1  10784    6.6000   150.0   22.7   460.106.00             708.7   1119.8    99.2   -         4762
2452632  11.4   4x  RTX_3090     6.3      16.0     64.0  35       2.0000   123.5   61.8   470.86                 84.6    84.4      99.3   3.8       4420
2450275  11.4   4x  RTX_3080_Ti  12.5     32.0    128.7  817      1.8000   128.8   71.6   470.82.00              278.3   350.4     99.7   -         4260
2449210  11.5   4x  RTX_3090     11.2     48.0    128.9  324      2.0000   89.7    44.9   495.29.05              688.3   775.4     99.8   -         2764
2445175  11.4   4x  RTX_3090     11.9     32.0    257.6  1530     2.0000   135.4   67.7   470.86                 868.6   887.1     99.7   25.9      3055
2444916  11.4   4x  RTX_3090     11.9     16.0    128.7  1576     1.4000   131.8   94.2   470.82.00              39.4    402.3     99.9   -         3759
2437188  11.4   4x  Tesla_P100   11.7     24.0     95.2  2945     0.7200   44.8    62.2   470.82.00              10.9    76.2      99.5   0.1       3969
2437179  11.4   4x  Tesla_P100   11.7     32.0    192.1  3070     0.7200   44.8    62.3   470.82.00              11.1    66.0      99.2   0.0       4159
2431606  11.4   4x  RTX_3090     17.9     32.0    110.7  330      1.8400   134.3   73.0   470.82.01              584.6   813.4     99.7   4.4       4079
2419191  11.4   4x  RTX_2080_Ti  6.3      32.0     64.4  837      2.0000   64.7    32.4   470.63.01              40.5    205.9     99.7   -         162
2405589  11.4   4x  RTX_2080_Ti  10.8     24.0    257.9  815      1.9000   62.8    33.0   470.82.00              389.4   608.8     100.0  1.8       2776
2392087  11.4   4x  RTX_A6000    10.8     32.0    515.9  1247     1.8000   64.5    35.8   470.94                 669.9   705.4     99.1   10.9      4782
2377227  11.2   4x  RTX_3090     6.3      24.0     64.3  1638     2.0000   128.3   64.1   460.32.03              37.8    145.0     99.7   3.0       2672
2349173  11.4   4x  RTX_3090     23.2     48.0    128.7  1475     2.0000   107.4   53.7   470.86                 33.2    84.2      99.8   47.3      3949
2338635  11.4   4x  RTX_3090     23.0     32.0    128.5  3151     1.6000   108.8   68.0   470.86                 33.8    86.4      99.6   47.4      3948
2303959  11.2   4x  RTX_3090     11.7     28.0    128.8  791      2.1200   131.3   61.9   460.32.03              519.7   570.7     99.5   -         3042
2281830  11.2   4x  A100_PCIE    18.1     32.0    515.9  2910     7.4000   143.6   19.4   460.91.03              478.2   655.5     99.9   28.7      2901
2193726  11.4   4x  RTX_3090     12.4     32.0    128.8  1646     3.6000   153.9   42.8   470.82.01              33.3    137.5     99.5   -         3434
1737692  11.2   4x  RTX_3070     6.3      28.0    128.5  656      2.8000   37.5    13.4   460.91.03              452.6   703.2     99.6   -         3510
```

#### Launching Instances
To create an instance of type 2459368 (using an ID from the search) with the vastai/tensorflow image
and 32 GB of disk storage

```./vast.py create instance 2459368 --image vastai/tensorflow --disk 32```

## Install

If you followed the instructions in [Quickstart](#Quickstart) you have already installed the script that contains
most of the CLI functionality. If you wish to print PDF format invoices you will need a few other
things. First, you'll need the vast_pdf.py script. This can be found in this repository in the main
directory at [vast_pdf.py](vast_pdf.py). This script should be present in the same directory as the
`vast.py` script. It makes use of a third party library called Borb to create the PDF invoices. To install
this run the command `pip3 install borb`

## Commands

The CLI API is all contained in a python script called `vast.py`.
This script can be called with various commands as arguments. Commands follow
a simple "verb-object" pattern. As an example, consider "show machines". To run this
command we type `./vast.py show machines`

## List of commands and associated help message

```
usage: vast.py [-h] [--url URL] [--retry RETRY] [--raw] [--explain] [--api-key API_KEY] command ...

positional arguments:
 command             command to run. one of:
  help               print this help message
  attach ssh         Attach an ssh key to an instance. This will allow you to connect to the instance with the ssh key
  cancel copy        Cancel a remote copy in progress, specified by DST id
  cancel sync        Cancel a remote copy in progress, specified by DST id
  change bid         Change the bid price for a spot/interruptible instance
  copy               Copy directories between instances and/or local
  vm copy            Copy VM image from one VM instance to another
  cloud copy         Copy files/folders to and from cloud providers
  create api-key     Create a new api-key with restricted permissions. Can be sent to other users and teammates
  create env-var     Create a new user environment variable
  create ssh-key     Create a new ssh-key
  create autogroup   Create a new autoscale group
  create endpoint    Create a new endpoint group
  create instance    Create a new instance
  create subaccount  Create a subaccount
  create team        Create a new team
  create team-role   Add a new role to your team
  create template    Create a new template
  delete api-key     Remove an api-key
  delete ssh-key     Remove an ssh-key
  delete autogroup   Delete an autogroup group
  delete endpoint    Delete an endpoint group
  delete env-var     Delete a user environment variable
  delete template    Delete a Template
  destroy instance   Destroy an instance (irreversible, deletes data)
  destroy instances  Destroy a list of instances (irreversible, deletes data)
  destroy team       Destroy your team
  detach ssh         Detach an ssh key from an instance
  execute            Execute a (constrained) remote command on a machine
  get endpt-logs     Fetch logs for a specific serverless endpoint group
  invite team-member
                     Invite a team member
  label instance     Assign a string label to an instance
  launch instance    Launch the top instance from the search offers based on the given parameters
  logs               Get the logs for an instance
  prepay instance    Deposit credits into reserved instance
  reboot instance    Reboot (stop/start) an instance
  recycle instance   Recycle (destroy/create) an instance
  remove team-member
                     Remove a team member
  remove team-role   Remove a role from your team
  reports            Get the user reports for a given machine
  reset api-key      Reset your api-key (get new key from website)
  start instance     Start a stopped instance
  start instances    Start a list of instances
  stop instance      Stop a running instance
  stop instances     Stop a list of instances
  search benchmarks  Search for benchmark results using custom query
  search invoices    Search for benchmark results using custom query
  search offers      Search for instance types using custom query
  search templates   Search for template results using custom query
  set api-key        Set api-key (get your api-key from the console/CLI)
  set user           Update user data from json file
  ssh-url            ssh url helper
  scp-url            scp url helper
  show api-key       Show an api-key
  show api-keys      List your api-keys associated with your account
  show audit-logs    Display account's history of important actions
  show ssh-keys      List your ssh keys associated with your account
  show autogroups    Display user's current autogroup groups
  show endpoints     Display user's current endpoint groups
  show connections   Display user's cloud connections
  show deposit       Display reserve deposit info for an instance
  show earnings      Get machine earning history reports
  show env-vars      Show user environment variables
  show invoices      Get billing history reports
  show instance      Display user's current instances
  show instances     Display user's current instances
  show ipaddrs       Display user's history of ip addresses
  show user          Get current user data
  show subaccounts   Get current subaccounts
  show team-members  Show your team members
  show team-role     Show your team role
  show team-roles    Show roles for a team
  transfer credit    Transfer credits to another account
  update autogroup   Update an existing autoscale group
  update endpoint    Update an existing endpoint group
  update env-var     Update an existing user environment variable
  update instance    Update recreate an instance from a new/updated template
  update team-role   Update an existing team role
  update template    Update an existing template
  update ssh-key     Update an existing ssh key
  cancel maint       [Host] Cancel maint window
  cleanup machine    [Host] Remove all expired storage instances from the machine, freeing up space
  delete machine     [Host] Delete machine if the machine is not being used by clients. host jobs on their own machines are disregarded and machine is force deleted.
  list machine       [Host] list a machine for rent
  list machines      [Host] list machines for rent
  remove defjob      [Host] Delete default jobs
  set defjob         [Host] Create default jobs for a machine
  set min-bid        [Host] Set the minimum bid/rental price for a machine
  schedule maint     [Host] Schedule upcoming maint window
  show machine       [Host] Show hosted machines
  show machines      [Host] Show hosted machines
  show maints        [Host] Show maintenance information for host machines
  unlist machine     [Host] Unlist a listed machine
  self-test machine  [Host] Perform a self-test on the specified machine

options:
 -h, --help          show this help message and exit
 --url URL           server REST api url
 --retry RETRY       retry limit
 --raw               output machine-readable json
 --explain           output verbose explanation of mapping of CLI calls to HTTPS API endpoints
 --api-key API_KEY   api key. defaults to using the one stored in /root/.config/vastai/vast_api_key

Use 'vast COMMAND --help' for more info about a command
```

## Self-Test a Machine (Single Machine)
Hosts can run a **self-test** to verify that a single machine meets necessary requirements and performs basic reliability & stress tests.

### Usage
```
./vast.py self-test machine <machine_id> [--ignore-requirements]
```

- **`machine_id`** is the numeric ID of the machine you want to self-test.
- **`--ignore-requirements`** (optional) will **print** which requirements your machine fails, but it will still continue the tests. If not passed, the self-test stops upon failing requirements.

Example:
```
# Standard self-test, respecting requirements
./vast.py self-test machine 12345

# Ignore system requirements and run anyway:
./vast.py self-test machine 12345 --ignore-requirements
```

**Typical Output:**

1. **Requirements Check**  
   Prints “Machine ID <id> does not meet the requirements” if any fail. Then either stops (if you didn’t use `--ignore-requirements`) or continues.  

2. **Instance Creation**  
   The CLI spins up a short-lived test instance on the machine.  

3. **Series of Tests**  
   - System & environment checks  
   - GPU tests (ResNet50, ECC test, etc.)  
   - Stress tests (stress-ng, gpu-burn)  

4. **Summary**  
   - `Test passed.` if everything works  
   - Or a reason if it fails (e.g. “No response for 60 seconds with running instance”)

At the end, the test instance is automatically **destroyed**.

---


## Host Machine Testing with `vast_machine_tester.py`

For **hosts** who want to **test multiple machines automatically**, we provide `vast_machine_tester.py`. It:

1. **Searches** for offers on your host (filters by `--host_id` or `--verified`).  
2. **Selects** the “best offer” for each machine (highest `dlperf`).  
3. **Spins up** concurrent self-tests on each machine.  
4. **Saves** results to:
   - `passed_machines.txt`
   - `failed_machines.txt`
5. **Outputs** a summary (including a table of failure reasons).
6. **(Optional)** Automatically **verifies** machines that pass, if `--auto-verify true`.

### Usage

```
python3 vast_machine_tester.py [--verified {true,false,any}] 
                               [--host_id HOST_ID] 
                               [--ignore-requirements] 
                               [--auto-verify {true,false}] {ADMIN API KEYS ONLY}
```

- **`--verified {true,false,any}`**  
  Which verification status to filter offers by. Defaults to `false`.

- **`--host_id HOST_ID`**  
  Filter offers by a specific host ID. `any` means no filter. Defaults to `any`.

- **`--ignore-requirements`**  
  Ignore the minimum system requirements check in each self-test. Requirement failures are logged but not blocking.

- **`--auto-verify {true,false}`**  Only works if admin api key is used. 
  If `"true"`, any machine that passes the self-test is automatically set to `"verified"`.  
  If `"false"` (or omitted), you’re prompted whether to verify each machine that passes. Defaults to `false`.

### Examples

1. **Test all unverified machines for a specific Host ID** (default verification filter is `false`):
   ```bash
   python3 vast_machine_tester.py --host_id 123456
   ```
   Saves results to `passed_machines.txt` and `failed_machines.txt`.

2. **Test *any* machines (verified or unverified)**:
   ```bash
   python3 vast_machine_tester.py --verified any --host_id 123456
   ```

3. **Ignore system requirements** (but still see them in logs):
   ```bash
   python3 vast_machine_tester.py --host_id 123456 --ignore-requirements
   ```

4. **Automatically verify machines that pass**:
   ```bash
   python3 vast_machine_tester.py --host_id 123456 --auto-verify true
   ```

### Output Files

- **`passed_machines.txt`**  
  Contains a timestamp and a **comma-separated** list of machine IDs that have passed.

- **`failed_machines.txt`**  
  Contains a timestamp and lines of the form `<machine_id>: <reason>` for each failure.

### Failure Summary

When tests finish, a short table is printed summarizing each unique failure reason (e.g., “Download speed <= 10 Mb/s”).

## Usage Examples

1. **Single machine, fail if not meeting requirements**:
   ```
   ./vast.py self-test machine 54321
   ```
   If it fails, you see the failing requirements in the output, and the test ends.

2. **Single machine, continue testing anyway**:
   ```
   ./vast.py self-test machine 54321 --ignore-requirements
   ```
   Prints the failure reasons but **still** runs the tests.  

3. **Multiple machines** from a single host ID, ignoring requirements:
   ```
   python3 vast_machine_tester.py --host_id 123456 --ignore-requirements
   ```
   In a few minutes, you’ll have **passed_machines.txt** and **failed_machines.txt** with a summary.

---

## Tab-Completion
Vast.py has optional tab completion in both the Bash and Zsh shell if the [argcomplete](https://github.com/kislyuk/argcomplete) package is installed. To enable this first install the `argcomplete` pip then either run `activate-global-python-argcomplete` to install global handlers or, for a local shell instance, `eval "$(register-python-argcomplete vast.py)"`. If necessary, change `vast.py` to whatever name you've assigned to invoke the tool as you are instrumenting the shell to autocomplete upon a certain command.

As a caveat, although we haven't seen it in the wild, as api calls may be executed with the tab complete, invoking it too rapidly could trigger a rate limit. Please report it in the github issues tab if you encounter it or other unexpected behavior.
