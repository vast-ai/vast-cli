"""Query parsing and field definitions for Vast.ai API.

This module is shared between the SDK and CLI layers.
"""

import re
import sys
import time
from datetime import datetime
from typing import Dict, List


def numeric_version(version_str):
    try:
        # Split the version string by the period
        major, minor, patch = version_str.split('.')

        # Pad each part with leading zeros to make it 3 digits
        major = major.zfill(3)
        minor = minor.zfill(3)
        patch = patch.zfill(3)

        # Concatenate the padded parts
        numeric_version_str = f"{major}{minor}{patch}"

        # Convert the concatenated string to an integer
        result = int(numeric_version_str)
        #print(result)
        return result

    except ValueError:
        print("Invalid version string format. Expected format: X.X.X")
        return None


def string_to_unix_epoch(date_string):
    if date_string is None:
        return None
    try:
        # Check if the input is a float or integer representing Unix time
        return float(date_string)
    except ValueError:
        # If not, parse it as a date string
        date_object = datetime.strptime(date_string, "%m/%d/%Y")
        return time.mktime(date_object.timetuple())

def fix_date_fields(query: Dict[str, Dict], date_fields: List[str]):
    """Takes in a query and date fields to correct and returns query with appropriate epoch dates"""
    new_query: Dict[str, Dict] = {}
    for field, sub_query in query.items():
        # fix date values for given date fields
        if field in date_fields:
            new_sub_query = {k: string_to_unix_epoch(v) for k, v in sub_query.items()}
            new_query[field] = new_sub_query
        # else, use the original
        else: new_query[field] = sub_query

    return new_query


def version_string_sort(a, b) -> int:
    """
    Accepts two version strings and decides whether a > b, a == b, or a < b.
    This is meant as a sort function to be used for the driver versions in which only
    the == operator currently works correctly. Not quite finished...

    :param str a:
    :param str b:
    :return int:
    """
    a_parts = a.split(".")
    b_parts = b.split(".")

    return 0


vol_offers_fields = {
        "cpu_arch",
        "cuda_vers",
        "cluster_id",
        "nw_disk_min_bw",
        "nw_disk_avg_bw",
        "nw_disk_max_bw",
        "datacenter",
        "disk_bw",
        "disk_space",
        "driver_version",
        "duration",
        "geolocation",
        "gpu_arch",
        "has_avx",
        "host_id",
        "id",
        "inet_down",
        "inet_up",
        "machine_id",
        "pci_gen",
        "pcie_bw",
        "reliability",
        "storage_cost",
        "static_ip",
        "total_flops",
        "ubuntu_version",
        "verified",
}


offers_fields = {
    "bw_nvlink",
    "compute_cap",
    "cpu_arch",
    "cpu_cores",
    "cpu_cores_effective",
    "cpu_ghz",
    "cpu_ram",
    "cuda_max_good",
    "datacenter",
    "direct_port_count",
    "driver_version",
    "disk_bw",
    "disk_space",
    "dlperf",
    "dlperf_per_dphtotal",
    "dph_total",
    "duration",
    "external",
    "flops_per_dphtotal",
    "gpu_arch",
    "gpu_display_active",
    "gpu_frac",
    # "gpu_ram_free_min",
    "gpu_mem_bw",
    "gpu_name",
    "gpu_ram",
    "gpu_total_ram",
    "gpu_display_active",
    "gpu_max_power",
    "gpu_max_temp",
    "has_avx",
    "host_id",
    "id",
    "inet_down",
    "inet_down_cost",
    "inet_up",
    "inet_up_cost",
    "machine_id",
    "min_bid",
    "mobo_name",
    "num_gpus",
    "pci_gen",
    "pcie_bw",
    "reliability",
    #"reliability2",
    "rentable",
    "rented",
    "storage_cost",
    "static_ip",
    "total_flops",
    "ubuntu_version",
    "verification",
    "verified",
    "vms_enabled",
    "geolocation",
    "cluster_id"
}

offers_alias = {
    "cuda_vers": "cuda_max_good",
    "display_active": "gpu_display_active",
    #"reliability": "reliability2",
    "dlperf_usd": "dlperf_per_dphtotal",
    "dph": "dph_total",
    "flops_usd": "flops_per_dphtotal",
}

offers_mult = {
    "cpu_ram": 1000,
    "gpu_ram": 1000,
    "gpu_total_ram" : 1000,
    "duration": 24.0 * 60.0 * 60.0,
}


benchmarks_fields = {
    "contract_id",#             int        ID of instance/contract reporting benchmark
    "id",#                      int        benchmark unique ID
    "image",#                   string     image used for benchmark
    "last_update",#             float      date of benchmark
    "machine_id",#              int        id of machine benchmarked
    "model",#                   string     name of model used in benchmark
    "name",#                    string     name of benchmark
    "num_gpus",#                int        number of gpus used in benchmark
    "score"#                   float      benchmark score result
}

invoices_fields = {
    'id',#               int,
    'user_id',#          int,
    'when',#             float,
    'paid_on',#          float,
    'payment_expected',# float,
    'amount_cents',#     int,
    'is_credit',#        bool,
    'is_delayed',#       bool,
    'balance_before',#   float,
    'balance_after',#    float,
    'original_amount',#  int,
    'event_id',#         string,
    'cut_amount',#       int,
    'cut_percent',#      float,
    'extra',#            json,
    'service',#          string,
    'stripe_charge',#    json,
    'stripe_refund',#    json,
    'stripe_payout',#    json,
    'error',#            json,
    'paypal_email',#     string,
    'transfer_group',#   string,
    'failed',#           bool,
    'refunded',#         bool,
    'is_check',#         bool,
}

templates_fields = {
    "creator_id",#              int        ID of creator
    "created_at",#              float      time of initial template creation (UTC epoch timestamp)
    "count_created",#           int        #instances created (popularity)
    "default_tag",#             string     image default tag
    "docker_login_repo",#       string     image docker repository
    "id",#                      int        template unique ID
    "image",#                   string     image used for benchmark
    "jup_direct",#              bool       supports jupyter direct
    "hash_id",#                 string     unique hash ID of template
    "private",#                 bool       true: only your templates, None: public templates
    "name",#                    string     displayable name
    "recent_create_date",#      float      last time of instance creation (UTC epoch timestamp)
    "recommended_disk_space",#  float      min disk space required
    "recommended",#             bool       is templated on our recommended list
    "ssh_direct",#              bool       supports ssh direct
    "tag",#                     string     image tag
    "use_ssh",#                 string     supports ssh (direct or proxy)
}


def parse_query(query_str: str, res: Dict = None, fields = {}, field_alias = {}, field_multiplier = {}) -> Dict:
    """
    Basically takes a query string (like the ones in the examples of commands for the search__offers function) and
    processes it into a dict of URL parameters to be sent to the server.

    :param str query_str:
    :param Dict res:
    :return Dict:
    """
    if query_str is None:
        return res

    if res is None: res = {}
    if type(query_str) == list:
        query_str = " ".join(query_str)
    query_str = query_str.strip()

    # Revised regex pattern to accurately capture quoted strings, bracketed lists, and single words/numbers
    #pattern    = r"([a-zA-Z0-9_]+)\s*(=|!=|<=|>=|<|>| in | nin | eq | neq | not eq | not in )?\s*(\"[^\"]*\"|\[[^\]]+\]|[^ ]+)"
    #pattern    = "([a-zA-Z0-9_]+)( *[=><!]+| +(?:[lg]te?|nin|neq|eq|not ?eq|not ?in|in) )?( *)(\[[^\]]+\]|[^ ]+)?( *)"
    pattern     = r"([a-zA-Z0-9_]+)( *[=><!]+| +(?:[lg]te?|nin|neq|eq|not ?eq|not ?in|in) )?( *)(\[[^\]]+\]|\"[^\"]+\"|[^ ]+)?( *)"
    opts        = re.findall(pattern, query_str)

    #print("parse_query regex:")
    #print(opts)

    #print(opts)
    # res = {}
    op_names = {
        ">=": "gte",
        ">": "gt",
        "gt": "gt",
        "gte": "gte",
        "<=": "lte",
        "<": "lt",
        "lt": "lt",
        "lte": "lte",
        "!=": "neq",
        "==": "eq",
        "=": "eq",
        "eq": "eq",
        "neq": "neq",
        "noteq": "neq",
        "not eq": "neq",
        "notin": "notin",
        "not in": "notin",
        "nin": "notin",
        "in": "in",
    }



    joined = "".join("".join(x) for x in opts)
    if joined != query_str:
        raise ValueError(
            "Unconsumed text. Did you forget to quote your query? " + repr(joined) + " != " + repr(query_str))

    for field, op, _, value, _ in opts:
        value = value.strip(",[]")
        v = res.setdefault(field, {})
        op = op.strip()
        op_name = op_names.get(op)

        if field in field_alias:
            res.pop(field)
            field = field_alias[field]

        if (field == "driver_version") and ('.' in value):
            value = numeric_version(value)

        if not field in fields:
            print("Warning: Unrecognized field: {}, see list of recognized fields.".format(field), file=sys.stderr);
        if not op_name:
            raise ValueError("Unknown operator. Did you forget to quote your query? " + repr(op).strip("u"))
        if op_name in ["in", "notin"]:
            value = [x.strip() for x in value.split(",") if x.strip()]
        if not value:
            raise ValueError("Value cannot be blank. Did you forget to quote your query? " + repr((field, op, value)))
        if not field:
            raise ValueError("Field cannot be blank. Did you forget to quote your query? " + repr((field, op, value)))
        if value in ["?", "*", "any"]:
            if op_name != "eq":
                raise ValueError("Wildcard only makes sense with equals.")
            if field in v:
                del v[field]
            if field in res:
                del res[field]
            continue

        if isinstance(value, str):
            value = value.replace('_', ' ')
            value = value.strip('\"')
        elif isinstance(value, list):
            value = [x.replace('_', ' ')    for x in value]
            value = [x.strip('\"')          for x in value]

        if field in field_multiplier:
            value = float(value) * field_multiplier[field]
            v[op_name] = value
        else:
            #print(value)
            if   (value == 'true') or (value == 'True'):
                v[op_name] = True
            elif (value == 'false') or (value == 'False'):
                v[op_name] = False
            elif (value == 'None') or (value == 'null'):
                v[op_name] = None
            else:
                v[op_name] = value

        if field not in res:
            res[field] = v
        else:
            res[field].update(v)
    #print(res)
    return res
