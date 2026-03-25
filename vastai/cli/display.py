"""Display formatting and field definitions for the Vast.ai CLI."""

import re
import shutil
import subprocess
from datetime import datetime
from typing import Dict, Tuple


def strip_strings(value):
    if isinstance(value, str):
        return value.strip()
    elif isinstance(value, dict):
        return {k: strip_strings(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [strip_strings(item) for item in value]
    return value  # Return as is if not a string, list, or dict

def translate_null_strings_to_blanks(d: Dict) -> Dict:
    """Map over a dict and translate any null string values into ' '.
    Leave everything else as is. This is needed because you cannot add TableCell
    objects with only a null string or the client crashes.

    :param Dict d: dict of item values.
    :rtype Dict:
    """

    # Beware: locally defined function.
    def translate_nulls(s):
        if s == "":
            return " "
        return s

    new_d = {k: translate_nulls(v) for k, v in d.items()}
    return new_d


def deindent(message: str, add_separator: bool = True) -> str:
    """
    Deindent a quoted string. Scans message and finds the smallest number of whitespace characters in any line and
    removes that many from the start of every line.

    :param str message: Message to deindent.
    :rtype str:
    """
    message = re.sub(r" *$", "", message, flags=re.MULTILINE)
    indents = [len(x) for x in re.findall("^ *(?=[^ ])", message, re.MULTILINE) if len(x)]
    a = min(indents)
    message = re.sub(r"^ {," + str(a) + "}", "", message, flags=re.MULTILINE)
    if add_separator:
        # For help epilogs - cleanly separating extra help from options
        line_width = min(150, shutil.get_terminal_size((80, 20)).columns)
        message = "_"*line_width + "\n"*2 + message.strip() + "\n" + "_"*line_width
    return message.strip()


# These are the fields that are displayed when a search is run
displayable_fields = (
    # ("bw_nvlink", "Bandwidth NVLink", "{}", None, True),
    ("id", "ID", "{}", None, True),
    ("cuda_max_good", "CUDA", "{:0.1f}", None, True),
    ("num_gpus", "N", "{}x", None, False),
    ("gpu_name", "Model", "{}", None, True),
    ("pcie_bw", "PCIE", "{:0.1f}", None, True),
    ("cpu_ghz", "cpu_ghz", "{:0.1f}", None, True),
    ("cpu_cores_effective", "vCPUs", "{:0.1f}", None, True),
    ("cpu_ram", "RAM", "{:0.1f}", lambda x: x / 1000, False),
    ("gpu_ram", "VRAM", "{:0.1f}", lambda x: x / 1000, False),
    ("disk_space", "Disk", "{:.0f}", None, True),
    ("dph_total", "$/hr", "{:0.4f}", None, True),
    ("dlperf", "DLP", "{:0.1f}", None, True),
    ("dlperf_per_dphtotal", "DLP/$", "{:0.2f}", None, True),
    ("score", "score", "{:0.1f}", None, True),
    ("driver_version", "NV Driver", "{}", None, True),
    ("inet_up", "Net_up", "{:0.1f}", None, True),
    ("inet_down", "Net_down", "{:0.1f}", None, True),
    ("reliability", "R", "{:0.1f}", lambda x: x * 100, True),
    ("duration", "Max_Days", "{:0.1f}", lambda x: x / (24.0 * 60.0 * 60.0), True),
    ("machine_id", "mach_id", "{}", None, True),
    ("verification", "status", "{}", None, True),
    ("host_id", "host_id", "{}", None, True),
    ("direct_port_count", "ports", "{}", None, True),
    ("geolocation", "country", "{}", None, True),
   #  ("direct_port_count", "Direct Port Count", "{}", None, True),
)

displayable_fields_reserved = (
    # ("bw_nvlink", "Bandwidth NVLink", "{}", None, True),
    ("id", "ID", "{}", None, True),
    ("cuda_max_good", "CUDA", "{:0.1f}", None, True),
    ("num_gpus", "N", "{}x", None, False),
    ("gpu_name", "Model", "{}", None, True),
    ("pcie_bw", "PCIE", "{:0.1f}", None, True),
    ("cpu_ghz", "cpu_ghz", "{:0.1f}", None, True),
    ("cpu_cores_effective", "vCPUs", "{:0.1f}", None, True),
    ("cpu_ram", "RAM", "{:0.1f}", lambda x: x / 1000, False),
    ("disk_space", "Disk", "{:.0f}", None, True),
    ("discounted_dph_total", "$/hr", "{:0.4f}", None, True),
    ("dlperf", "DLP", "{:0.1f}", None, True),
    ("dlperf_per_dphtotal", "DLP/$", "{:0.2f}", None, True),
    ("driver_version", "NV Driver", "{}", None, True),
    ("inet_up", "Net_up", "{:0.1f}", None, True),
    ("inet_down", "Net_down", "{:0.1f}", None, True),
    ("reliability", "R", "{:0.1f}", lambda x: x * 100, True),
    ("duration", "Max_Days", "{:0.1f}", lambda x: x / (24.0 * 60.0 * 60.0), True),
    ("machine_id", "mach_id", "{}", None, True),
    ("verification", "status", "{}", None, True),
    ("host_id", "host_id", "{}", None, True),
    ("direct_port_count", "ports", "{}", None, True),
    ("geolocation", "country", "{}", None, True),
   #  ("direct_port_count", "Direct Port Count", "{}", None, True),
)


vol_displayable_fields = (
    ("id", "ID", "{}", None, True),
    ("cuda_max_good", "CUDA", "{:0.1f}", None, True),
    ("cpu_ghz", "cpu_ghz", "{:0.1f}", None, True),
    ("disk_bw", "Disk B/W", "{:0.1f}", None, True),
    ("disk_space", "Disk", "{:.0f}", None, True),
    ("disk_name", "Disk Name", "{}", None, True),
    ("storage_cost", "$/Gb/Month", "{:.2f}", None, True),
    ("driver_version", "NV Driver", "{}", None, True),
    ("inet_up", "Net_up", "{:0.1f}", None, True),
    ("inet_down", "Net_down", "{:0.1f}", None, True),
    ("reliability", "R", "{:0.1f}", lambda x: x * 100, True),
    ("duration", "Max_Days", "{:0.1f}", lambda x: x / (24.0 * 60.0 * 60.0), True),
    ("machine_id", "mach_id", "{}", None, True),
    ("verification", "status", "{}", None, True),
    ("host_id", "host_id", "{}", None, True),
    ("geolocation", "country", "{}", None, True),
)

nw_vol_displayable_fields = (
    ("id", "ID", "{}", None, True),
    ("disk_space", "Disk", "{:.0f}", None, True),
    ("storage_cost", "$/Gb/Month", "{:.2f}", None, True),
    ("inet_up", "Net_up", "{:0.1f}", None, True),
    ("inet_down", "Net_down", "{:0.1f}", None, True),
    ("reliability", "R", "{:0.1f}", lambda x: x * 100, True),
    ("duration", "Max_Days", "{:0.1f}", lambda x: x / (24.0 * 60.0 * 60.0), True),
    ("verification", "status", "{}", None, True),
    ("host_id", "host_id", "{}", None, True),
    ("cluster_id", "cluster_id", "{}", None, True),
    ("geolocation", "country", "{}", None, True),
    ("nw_disk_min_bw", "Min BW MiB/s", "{}", None, True),
    ("nw_disk_max_bw", "Max BW MiB/s", "{}", None, True),
    ("nw_disk_avg_bw", "Avg BW MiB/s", "{}", None, True),

)

# These fields are displayed when you do 'show instances'
instance_fields = (
    ("id", "ID", "{}", None, True),
    ("machine_id", "Machine", "{}", None, True),
    ("actual_status", "Status", "{}", None, True),
    ("num_gpus", "Num", "{}x", None, False),
    ("gpu_name", "Model", "{}", None, True),
    ("gpu_util", "Util. %", "{:0.1f}", None, True),
    ("cpu_cores_effective", "vCPUs", "{:0.1f}", None, True),
    ("cpu_ram", "RAM", "{:0.1f}", lambda x: x / 1000, False),
    ("disk_space", "Storage", "{:.0f}", None, True),
    ("ssh_host", "SSH Addr", "{}", None, True),
    ("ssh_port", "SSH Port", "{}", None, True),
    ("dph_total", "$/hr", "{:0.4f}", None, True),
    ("image_uuid", "Image", "{}", None, True),
    # ("dlperf",              "DLPerf",   "{:0.1f}",  None, True),
    # ("dlperf_per_dphtotal", "DLP/$",    "{:0.1f}",  None, True),
    ("inet_up", "Net up", "{:0.1f}", None, True),
    ("inet_down", "Net down", "{:0.1f}", None, True),
    ("reliability2", "R", "{:0.1f}", lambda x: x * 100, True),
    ("label", "Label", "{}", None, True),
    ("duration", "age(hours)", "{:0.2f}",  lambda x: x/(3600.0), True),
    ("uptime_mins", "uptime(mins)", "{:0.2f}",  None, True),
)

cluster_fields = (
    ("id", "ID", "{}", None, True),
    ("subnet", "Subnet", "{}", None, True),
    ("node_count", "Nodes", "{}", None, True),
    ("manager_id", "Manager ID", "{}", None, True),
    ("manager_ip", "Manager IP", "{}", None, True),
    ("machine_ids", "Machine ID's", "{}", None, True)
)

network_disk_fields = (
    ("network_disk_id", "Network Disk ID", "{}", None, True),
    ("free_space", "Free Space (GB)", "{}", None, True),
    ("total_space", "Total Space (GB)", "{}", None, True),
)

network_disk_machine_fields = (
    ("machine_id", "Machine ID", "{}", None, True),
    ("mount_point", "Mount Point", "{}", None, True),
)

overlay_fields = (
    ("overlay_id", "Overlay ID", "{}", None, True),
    ("name", "Name", "{}", None, True),
    ("subnet", "Subnet", "{}", None, True),
    ("cluster_id", "Cluster ID", "{}", None, True),
    ("instance_count", "Instances", "{}", None, True),
    ("instances", "Instance IDs", "{}", None, True),
)
volume_fields = (
    ("id", "ID", "{}", None, True),
    ("cluster_id", "Cluster ID", "{}", None, True),
    ("label", "Name", "{}", None, True),
    ("disk_space", "Disk", "{:.0f}", None, True),
    ("status", "status", "{}", None, True),
    ("disk_name", "Disk Name", "{}", None, True),
    ("driver_version", "NV Driver", "{}", None, True),
    ("inet_up", "Net_up", "{:0.1f}", None, True),
    ("inet_down", "Net_down", "{:0.1f}", None, True),
    ("reliability2", "R", "{:0.1f}", lambda x: x * 100, True),
    ("duration", "age(hours)", "{:0.2f}", lambda x: x/(3600.0), True),
    ("machine_id", "mach_id", "{}", None, True),
    ("verification", "Verification", "{}", None, True),
    ("host_id", "host_id", "{}", None, True),
    ("geolocation", "country", "{}", None, True),
    ("instances", "instances","{}", None, True)
)

# These fields are displayed when you do 'show machines'
machine_fields = (
    ("id", "ID", "{}", None, True),
    ("num_gpus", "#gpus", "{}", None, True),
    ("gpu_name", "gpu_name", "{}", None, True),
    ("disk_space", "disk", "{}", None, True),
    ("hostname", "hostname", "{}", lambda x: x[:16], True),
    ("driver_version", "driver", "{}", None, True),
    ("reliability2", "reliab", "{:0.4f}", None, True),
    ("verification", "veri", "{}", None, True),
    ("public_ipaddr", "ip", "{}", None, True),
    ("geolocation", "geoloc", "{}", None, True),
    ("num_reports", "reports", "{}", None, True),
    ("listed_gpu_cost", "gpuD_$/h", "{:0.2f}", None, True),
    ("min_bid_price", "gpuI$/h", "{:0.2f}", None, True),
    ("credit_discount_max", "rdisc", "{:0.2f}", None, True),
    ("listed_inet_up_cost",   "netu_$/TB", "{:0.2f}", lambda x: x * 1024, True),
    ("listed_inet_down_cost", "netd_$/TB", "{:0.2f}", lambda x: x * 1024, True),
    ("gpu_occupancy", "occup", "{}", None, True),
)

# These fields are displayed when you do 'show maints'
maintenance_fields = (
    ("machine_id", "Machine ID", "{}", None, True),
    ("start_time", "Start (Date/Time)", "{}", lambda x: datetime.fromtimestamp(x).strftime('%Y-%m-%d/%H:%M'), True),
    ("end_time", "End (Date/Time)", "{}", lambda x: datetime.fromtimestamp(x).strftime('%Y-%m-%d/%H:%M'), True),
    ("duration_hours", "Duration (Hrs)", "{}", None, True),
    ("maintenance_category", "Category", "{}", None, True),
)


ipaddr_fields = (
    ("ip", "ip", "{}", None, True),
    ("first_seen", "first_seen", "{}", None, True),
    ("first_location", "first_location", "{}", None, True),
)

audit_log_fields = (
    ("ip_address", "ip_address", "{}", None, True),
    ("api_key_id", "api_key_id", "{}", None, True),
    ("created_at", "created_at", "{}", None, True),
    ("api_route", "api_route", "{}", None, True),
    ("args", "args", "{}", None, True),
)


scheduled_jobs_fields = (
    ("id", "Scheduled Job ID", "{}", None, True),
    ("instance_id", "Instance ID", "{}", None, True),
    ("api_endpoint", "API Endpoint", "{}", None, True),
    ("start_time", "Start (Date/Time in UTC)", "{}", lambda x: datetime.fromtimestamp(x).strftime('%Y-%m-%d/%H:%M'), True),
    ("end_time", "End (Date/Time in UTC)", "{}", lambda x: datetime.fromtimestamp(x).strftime('%Y-%m-%d/%H:%M'), True),
    ("day_of_the_week", "Day of the Week", "{}", None, True),
    ("hour_of_the_day", "Hour of the Day in UTC", "{}", None, True),
    ("min_of_the_hour", "Minute of the Hour", "{}", None, True),
    ("frequency", "Frequency", "{}", None, True),
)

invoice_fields = (
    ("description", "Description", "{}", None, True),
    ("quantity", "Quantity", "{}", None, True),
    ("rate", "Rate", "{}", None, True),
    ("amount", "Amount", "{}", None, True),
    ("timestamp", "Timestamp", "{:0.1f}", None, True),
    ("type", "Type", "{}", None, True)
)

user_fields = (
    # ("api_key", "api_key", "{}", None, True),
    ("balance", "Balance", "{}", None, True),
    ("balance_threshold", "Bal. Thld", "{}", None, True),
    ("balance_threshold_enabled", "Bal. Thld Enabled", "{}", None, True),
    ("billaddress_city", "City", "{}", None, True),
    ("billaddress_country", "Country", "{}", None, True),
    ("billaddress_line1", "Addr Line 1", "{}", None, True),
    ("billaddress_line2", "Addr line 2", "{}", None, True),
    ("billaddress_zip", "Zip", "{}", None, True),
    ("billed_expected", "Billed Expected", "{}", None, True),
    ("billed_verified", "Billed Vfy", "{}", None, True),
    ("billing_creditonly", "Billing Creditonly", "{}", None, True),
    ("can_pay", "Can Pay", "{}", None, True),
    ("credit", "Credit", "{:0.2f}", None, True),
    ("email", "Email", "{}", None, True),
    ("email_verified", "Email Vfy", "{}", None, True),
    ("fullname", "Full Name", "{}", None, True),
    ("got_signup_credit", "Got Signup Credit", "{}", None, True),
    ("has_billing", "Has Billing", "{}", None, True),
    ("has_payout", "Has Payout", "{}", None, True),
    ("id", "Id", "{}", None, True),
    ("last4", "Last4", "{}", None, True),
    ("paid_expected", "Paid Expected", "{}", None, True),
    ("paid_verified", "Paid Vfy", "{}", None, True),
    ("password_resettable", "Pwd Resettable", "{}", None, True),
    ("paypal_email", "Paypal Email", "{}", None, True),
    ("ssh_key", "Ssh Key", "{}", None, True),
    ("user", "User", "{}", None, True),
    ("username", "Username", "{}", None, True)
)

connection_fields = (
    ("id", "ID", "{}", None, True),
    ("name", "NAME", "{}", None, True),
    ("cloud_type", "Cloud Type", "{}", None, True),
)


# ANSI escape codes for background/foreground colors
BG_DARK_GRAY = '\033[40m'  # Dark gray background
BG_LIGHT_GRAY = '\033[48;5;240m' # Light gray background
FG_WHITE = '\033[97m'            # Bright white text
BG_RESET = '\033[0m'             # Reset all formatting

def display_table(rows: list, fields: Tuple, replace_spaces: bool = True, auto_width: bool = True) -> None:
    """Basically takes a set of field names and rows containing the corresponding data and prints a nice tidy table
    of it.

    :param list rows: Each row is a dict with keys corresponding to the field names (first element) in the fields tuple.

    :param Tuple fields: 5-tuple describing a field. First element is field name, second is human readable version, third is format string, fourth is a lambda function run on the data in that field, fifth is a bool determining text justification. True = left justify, False = right justify. Here is an example showing the tuples in action.

    :rtype None:

    Example of 5-tuple: ("cpu_ram", "RAM", "{:0.1f}", lambda x: x / 1000, False)
    """
    header = [name for _, name, _, _, _ in fields]
    out_rows = [header]
    lengths = [len(x) for x in header]
    for instance in rows:
        row = []
        out_rows.append(row)
        for key, name, fmt, conv, _ in fields:
            conv = conv or (lambda x: x)
            val = instance.get(key, None)
            if val is None:
                s = "-"
            else:
                val = conv(val)
                s = fmt.format(val)
            if replace_spaces:
                s = s.replace(' ', '_')
            idx = len(row)
            lengths[idx] = max(len(s), lengths[idx])
            row.append(s)

    if auto_width:
        width = shutil.get_terminal_size((80, 20)).columns
        start_col_idxs = [0]
        total_len = 4  # +6ch for row label and -2ch for missing last sep in "  ".join()
        for i, l in enumerate(lengths):
            total_len += l + 2
            if total_len > width:
                start_col_idxs.append(i)  # index for the start of the next group
                total_len = l + 6         # l + 2 + the 4 from the initial length

        groups = {}
        for row in out_rows:
            grp_num = 0
            for i in range(len(start_col_idxs)):
                start = start_col_idxs[i]
                end = start_col_idxs[i+1]-1 if i+1 < len(start_col_idxs) else len(lengths)
                groups.setdefault(grp_num, []).append(row[start:end])
                grp_num += 1

        for i, group in groups.items():
            idx = start_col_idxs[i]
            group_lengths = lengths[idx:idx+len(group[0])]
            for row_num, row in enumerate(group):
                bg_color = BG_DARK_GRAY if (row_num - 1) % 2 else BG_LIGHT_GRAY
                row_label = "  #" if row_num == 0 else f"{row_num:3d}"
                out = [row_label]
                for l, s, f in zip(group_lengths, row, fields[idx:idx+len(row)]):
                    _, _, _, _, ljust = f
                    if ljust: s = s.ljust(l)
                    else:     s = s.rjust(l)
                    out.append(s)
                print(bg_color + FG_WHITE + "  ".join(out) + BG_RESET)
            print()
    else:
        for row in out_rows:
            out = []
            for l, s, f in zip(lengths, row, fields):
                _, _, _, _, ljust = f
                if ljust:
                    s = s.ljust(l)
                else:
                    s = s.rjust(l)
                out.append(s)
            print("  ".join(out))


def print_or_page(args, text):
    """ Print text to terminal, or pipe to pager_cmd if too long. """
    line_threshold = shutil.get_terminal_size(fallback=(80, 24)).lines
    lines = text.splitlines()
    if not args.full and len(lines) > line_threshold:
        pager_cmd = ['less', '-R'] if shutil.which('less') else None
        if pager_cmd:
            proc = subprocess.Popen(pager_cmd, stdin=subprocess.PIPE)
            proc.communicate(input=text.encode())
            return True
        else:
            print(text)
            return False
    else:
        print(text)
        return False
