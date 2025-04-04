#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

from __future__ import unicode_literals, print_function

import re
import json
import sys
import argparse
import os
import time
from typing import Dict, List, Tuple, Optional
from datetime import date, datetime, timedelta
import hashlib
import math
import threading
from concurrent.futures import ThreadPoolExecutor
import requests
import getpass
import subprocess
from subprocess import PIPE
import urllib3
import atexit
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from typing import Optional
import shutil
import logging
import textwrap
from pathlib import Path
import warnings

from utils.version_checker import check_for_update, get_local_version

ARGS = None
TABCOMPLETE = False
try:
    import argcomplete
    TABCOMPLETE = True
except:
    # No tab-completion for you
    pass

try:
    from urllib import quote_plus  # Python 2.X
except ImportError:
    from urllib.parse import quote_plus  # Python 3+

try:
    JSONDecodeError = json.JSONDecodeError
except AttributeError:
    JSONDecodeError = ValueError

try:
    input = raw_input
except NameError:
    pass


#server_url_default = "https://vast.ai"
server_url_default = "https://console.vast.ai"
# server_url_default = "http://localhost:5002"
#server_url_default = "host.docker.internal"
#server_url_default = "http://localhost:5002"
#server_url_default  = "https://vast.ai/api/v0"

logging.basicConfig(
    level=os.getenv("LOGLEVEL") or logging.WARN,
    format="%(levelname)s - %(message)s"
)

#TODO  - Change this when ready to go to prod, yes
APP_NAME = "vast-cli-fork"
VERSION = get_local_version()

try:
  # Although xdg-base-dirs is the newer name, there's 
  # python compatibility issues with dependencies that
  # can be unresolvable using things like python 3.9
  # So we actually use the older name, thus older
  # version for now. This is as of now (2024/11/15)
  # the safer option. -cjm
  import xdg

  DIRS = {
      'config': xdg.xdg_config_home(),
      'temp': xdg.xdg_cache_home()
  }

except:
  # Reasonable defaults.
  DIRS = {
      'config': os.path.join(os.getenv('HOME'), '.config'),
      'temp': os.path.join(os.getenv('HOME'), '.cache'),
  }

for key in DIRS.keys():
  DIRS[key] = path = os.path.join(DIRS[key], APP_NAME)
  if not os.path.exists(path):
    os.makedirs(path)

CACHE_FILE = os.path.join(DIRS['temp'], "gpu_names_cache.json")
CACHE_DURATION = timedelta(hours=24)

APIKEY_FILE = os.path.join(DIRS['config'], "vast_api_key")
APIKEY_FILE_HOME = os.path.expanduser("~/.vast_api_key") # Legacy

if not os.path.exists(APIKEY_FILE) and os.path.exists(APIKEY_FILE_HOME):
  print(f'copying key from {APIKEY_FILE_HOME} -> {APIKEY_FILE}')
  shutil.copyfile(APIKEY_FILE_HOME, APIKEY_FILE)


api_key_guard = object()

headers = {}


class Object(object):
    pass

def strip_strings(value):
    if isinstance(value, str):
        return value.strip()
    elif isinstance(value, dict):
        return {k: strip_strings(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [strip_strings(item) for item in value]
    return value  # Return as is if not a string, list, or dict

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


class argument(object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class hidden_aliases(object):
    # just a bit of a hack
    def __init__(self, l):
        self.l = l

    def __iter__(self):
        return iter(self.l)

    def __bool__(self):
        return False

    def __nonzero__(self):
        return False

    def append(self, x):
        self.l.append(x)

def http_get(args, req_url, headers = None, json = None):
    t = 0.15
    for i in range(0, args.retry):
        r = requests.get(req_url, headers=headers, json=json)
        if (r.status_code == 429):
            time.sleep(t)
            t *= 1.5
        else:
            break
    return r

def http_put(args, req_url, headers, json):
    t = 0.3
    for i in range(0, int(args.retry)):
        r = requests.put(req_url, headers=headers, json=json)
        if (r.status_code == 429):
            time.sleep(t)
            t *= 1.5
        else:
            break
    return r

def http_post(args, req_url, headers, json={}):
    t = 0.3
    for i in range(0, int(args.retry)):
        #if (args.explain):
        #    print(req_url)
        r = requests.post(req_url, headers=headers, json=json)
        if (r.status_code == 429):
            time.sleep(t)
            t *= 1.5
        else:
            break
    return r

def http_del(args, req_url, headers, json={}):
    t = 0.3
    for i in range(0, int(args.retry)):
        r = requests.delete(req_url, headers=headers, json=json)
        if (r.status_code == 429):
            time.sleep(t)
            t *= 1.5
        else:
            break
    return r


def load_permissions_from_file(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def complete_instance_machine(prefix=None, action=None, parser=None, parsed_args=None):
  return show__instances(ARGS, {'internal': True, 'field': 'machine_id'})

def complete_instance(prefix=None, action=None, parser=None, parsed_args=None):
  return show__instances(ARGS, {'internal': True, 'field': 'id'})

def complete_sshkeys(prefix=None, action=None, parser=None, parsed_args=None):
  return [str(m) for m in Path.home().joinpath('.ssh').glob('*.pub')]

class apwrap(object):
    def __init__(self, *args, **kwargs):
        if "formatter_class" not in kwargs:
            kwargs["formatter_class"] = MyWideHelpFormatter    
        self.parser = argparse.ArgumentParser(*args, **kwargs)
        self.parser.set_defaults(func=self.fail_with_help)
        self.subparsers_ = None
        self.subparser_objs = []
        self.added_help_cmd = False
        self.post_setup = []
        self.verbs = set()
        self.objs = set()

    def fail_with_help(self, *a, **kw):
        self.parser.print_help(sys.stderr)
        raise SystemExit

    def add_argument(self, *a, **kw):
        if not kw.get("parent_only"):
            for x in self.subparser_objs:
                try:
                    x.add_argument(*a, **kw)
                except argparse.ArgumentError:
                    # duplicate - or maybe other things, hopefully not
                    pass
        return self.parser.add_argument(*a, **kw)

    def subparsers(self, *a, **kw):
        if self.subparsers_ is None:
            kw["metavar"] = "command"
            kw["help"] = "command to run. one of:"
            self.subparsers_ = self.parser.add_subparsers(*a, **kw)
        return self.subparsers_

    def get_name(self, verb, obj):
        if obj:
            self.verbs.add(verb)
            self.objs.add(obj)
            name = verb + ' ' + obj
        else:
            self.objs.add(verb)
            name = verb
        return name

    def command(self, *arguments, aliases=(), help=None, **kwargs):
        help_ = help
        if not self.added_help_cmd:
            self.added_help_cmd = True

            @self.command(argument("subcommand", default=None, nargs="?"), help="print this help message")
            def help(*a, **kw):
                self.fail_with_help()

        def inner(func):
            dashed_name = func.__name__.replace("_", "-")
            verb, _, obj = dashed_name.partition("--")
            name = self.get_name(verb, obj)
            aliases_transformed = [] if aliases else hidden_aliases([])
            for x in aliases:
                verb, _, obj = x.partition(" ")
                aliases_transformed.append(self.get_name(verb, obj))
            if "formatter_class" not in kwargs:
                kwargs["formatter_class"] = MyWideHelpFormatter

            sp = self.subparsers().add_parser(name, aliases=aliases_transformed, help=help_, **kwargs)

            # TODO: Sometimes the parser.command has a help parameter. Ideally
            # I'd extract this during the sdk phase but for the life of me
            # I can't find it.
            setattr(func, "mysignature", sp)
            setattr(func, "mysignature_help", help_)

            self.subparser_objs.append(sp)
            for arg in arguments:
                tsp = sp.add_argument(*arg.args, **arg.kwargs)
                myCompleter= None
                comparator = arg.args[0].lower()
                if comparator.startswith('machine'):
                  myCompleter = complete_instance_machine
                elif comparator.startswith('id') or comparator.endswith('id'):
                  myCompleter = complete_instance
                elif comparator.startswith('ssh'):
                  myCompleter = complete_sshkeys
                  
                if myCompleter:
                  setattr(tsp, 'completer', myCompleter)


            sp.set_defaults(func=func)
            return func

        if len(arguments) == 1 and type(arguments[0]) != argument:
            func = arguments[0]
            arguments = []
            return inner(func)
        return inner

    def parse_args(self, argv=None, *a, **kw):
        if argv is None:
            argv = sys.argv[1:]
        argv_ = []
        for x in argv:
            if argv_ and argv_[-1] in self.verbs:
                argv_[-1] += " " + x
            else:
                argv_.append(x)
        args = self.parser.parse_args(argv_, *a, **kw)
        for func in self.post_setup:
            func(args)
        return args

class MyWideHelpFormatter(argparse.RawTextHelpFormatter):
    def __init__(self, prog):
        super().__init__(prog, width=128, max_help_position=50, indent_increment=1)


parser = apwrap(
    epilog="Use 'vast COMMAND --help' for more info about a command",
    formatter_class=MyWideHelpFormatter
)

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

    #req_url = apiurl(args, "/instances", {"owner": "me"});


def apiurl(args: argparse.Namespace, subpath: str, query_args: Dict = None) -> str:
    """Creates the endpoint URL for a given combination of parameters.

    :param argparse.Namespace args: Namespace with many fields relevant to the endpoint.
    :param str subpath: added to end of URL to further specify endpoint.
    :param typing.Dict query_args: specifics such as API key and search parameters that complete the URL.
    :rtype str:
    """
    result = None

    if query_args is None:
        query_args = {}
    if args.api_key is not None:
        query_args["api_key"] = args.api_key
    
    query_json = None

    if query_args:
        # a_list      = [<expression> for <l-expression> in <expression>]
        '''
        vector result;
        for (l_expression: expression) {
            result.push_back(expression);
        }
        '''
        # an_iterator = (<expression> for <l-expression> in <expression>)

        query_json = "&".join(
            "{x}={y}".format(x=x, y=quote_plus(y if isinstance(y, str) else json.dumps(y))) for x, y in
            query_args.items())
        
        result = args.url + "/api/v0" + subpath + "?" + query_json
    else:
        result = args.url + "/api/v0" + subpath

    if (args.explain):
        print("query args:")
        print(query_args)
        print("")
        print(f"base: {args.url + '/api/v0' + subpath + '?'} + query: ")
        print(result)
        print("")
    return result

def apiheaders(args: argparse.Namespace) -> Dict:
    """Creates the headers for a given combination of parameters.

    :param argparse.Namespace args: Namespace with many fields relevant to the endpoint.
    :rtype Dict:
    """
    result = {}
    if args.api_key is not None:
        result["Authorization"] = "Bearer " + args.api_key
    return result 


def deindent(message: str) -> str:
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


vol_offers_fields = {
        "cpu_arch",
        "cuda_vers",
        "datacenter",
        "disk_bw",
        "disk_space",
        "driver_version",
        "duration",
        "geolocation",
        "gpu_arch",
        "has_avx",
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

# Need to add bw_nvlink, machine_id, direct_port_count to output.


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

volume_fields = (
    ("id", "ID", "{}", None, True),
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
    ("maintenance_reason", "Reason", "{}", None, True),
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
    "geolocation"
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


def display_table(rows: list, fields: Tuple, replace_spaces: bool = True) -> None:
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


class VRLException(Exception):
    pass

def parse_vast_url(url_str):
    """
    Breaks up a vast-style url in the form instance_id:path and does
    some basic sanity type-checking.

    :param url_str:
    :return:
    """

    instance_id = None
    path = url_str
    #print(f'url_str: {url_str}')
    if (":" in url_str):
        url_parts = url_str.split(":", 2)
        if len(url_parts) == 2:
            (instance_id, path) = url_parts
        else:
            raise VRLException("Invalid VRL (Vast resource locator).")
        try:
            instance_id = int(instance_id)
        except:
            raise VRLException("Instance id must be an integer.")
    else:
        try:
            instance_id = int(path)
            path = "/"
        except:
            pass

    valid_unix_path_regex = re.compile('^(/)?([^/\0]+(/)?)+$')
    # Got this regex from https://stackoverflow.com/questions/537772/what-is-the-most-correct-regular-expression-for-a-unix-file-path
    if (path != "/") and (valid_unix_path_regex.match(path) is None):
        raise VRLException(f"Path component: {path} of VRL is not a valid Unix style path.")
    
    #print(f'instance_id: {instance_id}')
    #print(f'path: {path}')
    return (instance_id, path)

def get_ssh_key(argstr):
    ssh_key = argstr
    # Including a path to a public key is pretty reasonable.
    if os.path.exists(argstr):
      with open(argstr) as f:
        ssh_key = f.read()

    if "PRIVATE KEY" in ssh_key:
      raise ValueError(deindent("""
        🐴 Woah, hold on there, partner!

        That's a *private* SSH key.  You need to give the *public* 
        one. It usually starts with 'ssh-rsa', is on a single line, 
        has around 200 or so "base64" characters and ends with 
        some-user@some-where. "Generate public ssh key" would be 
        a good search term if you don't know how to do this.
      """))

    if not ssh_key.lower().startswith('ssh'):
      raise ValueError(deindent("""
        Are you sure that's an SSH public key?

        Usually it starts with the stanza 'ssh-(keytype)' 
        where the keytype can be things such as rsa, ed25519-sk, 
        or dsa. What you passed me was:

        {}

        And welp, that just don't look right.
      """.format(ssh_key)))

    return ssh_key


@parser.command(
    argument("instance_id", help="id of instance to attach to", type=int),
    argument("ssh_key", help="ssh key to attach to instance", type=str),
    usage="vastai attach instance_id ssh_key",
    help="Attach an ssh key to an instance. This will allow you to connect to the instance with the ssh key",
    epilog=deindent("""
        Attach an ssh key to an instance. This will allow you to connect to the instance with the ssh key.

        Examples:
         vast attach 12371 ssh-rsa AAAAB3NzaC1yc2EAAA...
         vast attach 12371 ssh-rsa $(cat ~/.ssh/id_rsa)

        The first example attaches the ssh key to instance 12371
    """),
)
def attach__ssh(args):
    ssh_key = get_ssh_key(args.ssh_key)
    url = apiurl(args, "/instances/{id}/ssh/".format(id=args.instance_id))
    req_json = {"ssh_key": ssh_key}
    r = http_post(args, url, headers=headers, json=req_json)
    r.raise_for_status()
    print(r.json())

@parser.command(
    argument("dst", help="instance_id:/path to target of copy operation", type=str),
    usage="vastai cancel copy DST",
    help="Cancel a remote copy in progress, specified by DST id",
    epilog=deindent("""
        Use this command to cancel any/all current remote copy operations copying to a specific named instance, given by DST.

        Examples:
         vast cancel copy 12371

        The first example cancels all copy operations currently copying data into instance 12371

    """),
)
def cancel__copy(args: argparse.Namespace):
    """
    Cancel a remote copy in progress, specified by DST id"

    @param dst: ID of copy instance Target to cancel.
    """

    url = apiurl(args, f"/commands/copy_direct/")
    dst_id = args.dst
    if (dst_id is None):
        print("invalid arguments")
        return

    print(f"canceling remote copies to {dst_id} ")

    req_json = { "client_id": "me", "dst_id": dst_id, }
    r = http_del(args, url, headers=headers,json=req_json)
    r.raise_for_status()
    if (r.status_code == 200):
        rj = r.json();
        if (rj["success"]):
            print("Remote copy canceled - check instance status bar for progress updates (~30 seconds delayed).")
        else:
            print(rj["msg"]);
    else:
        print(r.text);
        print("failed with error {r.status_code}".format(**locals()));


@parser.command(
    argument("dst", help="instance_id:/path to target of sync operation", type=str),
    usage="vastai cancel sync DST",
    help="Cancel a remote copy in progress, specified by DST id",
    epilog=deindent("""
        Use this command to cancel any/all current remote cloud sync operations copying to a specific named instance, given by DST.

        Examples:
         vast cancel sync 12371

        The first example cancels all copy operations currently copying data into instance 12371

    """),
)
def cancel__sync(args: argparse.Namespace):
    """
    Cancel a remote cloud sync in progress, specified by DST id"

    @param dst: ID of cloud sync instance Target to cancel.
    """

    url = apiurl(args, f"/commands/rclone/")
    dst_id = args.dst
    if (dst_id is None):
        print("invalid arguments")
        return

    print(f"canceling remote copies to {dst_id} ")

    req_json = { "client_id": "me", "dst_id": dst_id, }
    r = http_del(args, url, headers=headers,json=req_json)
    r.raise_for_status()
    if (r.status_code == 200):
        rj = r.json();
        if (rj["success"]):
            print("Remote copy canceled - check instance status bar for progress updates (~30 seconds delayed).")
        else:
            print(rj["msg"]);
    else:
        print(r.text);
        print("failed with error {r.status_code}".format(**locals()));



@parser.command(
    argument("id", help="id of instance type to change bid", type=int),
    argument("--price", help="per machine bid price in $/hour", type=float),
    usage="vastai change bid id [--price PRICE]",
    help="Change the bid price for a spot/interruptible instance",
    epilog=deindent("""
        Change the current bid price of instance id to PRICE.
        If PRICE is not specified, then a winning bid price is used as the default.
    """),
)
def change__bid(args: argparse.Namespace):
    """Alter the bid with id contained in args.

    :param argparse.Namespace args: should supply all the command-line options
    :rtype int:
    """
    url = apiurl(args, "/instances/bid_price/{id}/".format(id=args.id))

    json_blob = {"client_id": "me", "price": args.price,}
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, url, headers=headers, json=json_blob)
    r.raise_for_status()
    print("Per gpu bid price changed".format(r.json()))



@parser.command(
    argument("source", help="id of volume contract being cloned", type=int),
    argument("dest", help="id of volume offer volume is being copied to", type=int),
    argument("-s", "--size", help="Size of new volume contract, in GB. Must be greater than or equal to the source volume, and less than or equal to the destination offer.", type=float),
    argument("-d", "--disable_compression", action="store_true", help="Do not compress volume data before copying."),
    usage="vastai copy volume <source_id> <dest_id> [options]",
    help="Clone an existing volume",
    epilog=deindent("""
        Create a new volume with the given offer, by copying the existing volume. 
        Size defaults to the size of the existing volume, but can be increased if there is available space.
    """)
)
def clone__volume(args: argparse.Namespace):
    json_blob={
        "source" : args.source,
        "dest": args.dest,
    }
    if args.size:
        json_blob["size"] = args.size
    if args.disable_compression:
        json_blob["disable_compression"] = True


    url = apiurl(args, "/volumes/copy/")

    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_post(args, url,  headers=headers,json=json_blob)
    r.raise_for_status()
    if args.raw:
        return r
    else:
        print("Created. {}".format(r.json()))


@parser.command(
    argument("src", help="instance_id:/path to source of object to copy", type=str),
    argument("dst", help="instance_id:/path to target of copy operation", type=str),
    argument("-i", "--identity", help="Location of ssh private key", type=str),
    usage="vastai copy SRC DST",
    help="Copy directories between instances and/or local",
    epilog=deindent("""
        Copies a directory from a source location to a target location. Each of source and destination
        directories can be either local or remote, subject to appropriate read and write
        permissions required to carry out the action. The format for both src and dst is [instance_id:]path.
                    
        You should not copy to /root or / as a destination directory, as this can mess up the permissions on your instance ssh folder, breaking future copy operations (as they use ssh authentication)
        You can see more information about constraints here: https://vast.ai/docs/gpu-instances/data-movement#constraints
                    
        Examples:
         vast copy 6003036:/workspace/ 6003038:/workspace/
         vast copy 11824:/data/test data/test
         vast copy data/test 11824:/data/test

        The first example copy syncs all files from the absolute directory '/workspace' on instance 6003036 to the directory '/workspace' on instance 6003038.
        The second example copy syncs the relative directory 'data/test' on the local machine from '/data/test' in instance 11824.
        The third example copy syncs the directory '/data/test' in instance 11824 from the relative directory 'data/test' on the local machine.
    """),
)
def copy(args: argparse.Namespace):
    """
    Transfer data from one instance to another.

    @param src: Location of data object to be copied.
    @param dst: Target to copy object to.
    """

    (src_id, src_path) = parse_vast_url(args.src)
    (dst_id, dst_path) = parse_vast_url(args.dst)
    if (src_id is None) and (dst_id is None):
        pass
        #print("invalid arguments")
        #return

    print(f"copying {str(src_id)+':' if src_id else ''}{src_path} {str(dst_id)+':' if dst_id else ''}{dst_path}")

    req_json = {
        "client_id": "me",
        "src_id": src_id,
        "dst_id": dst_id,
        "src_path": src_path,
        "dst_path": dst_path,
    }
    if (args.explain):
        print("request json: ")
        print(req_json)
    if (src_id is None) or (dst_id is None):
        url = apiurl(args, f"/commands/rsync/")
    else:
        url = apiurl(args, f"/commands/copy_direct/")
    r = http_put(args, url,  headers=headers,json=req_json)
    r.raise_for_status()
    if (r.status_code == 200):
        rj = r.json()
        #print(json.dumps(rj, indent=1, sort_keys=True))
        if (rj["success"]) and ((src_id is None) or (dst_id is None)):
            homedir = subprocess.getoutput("echo $HOME")
            #print(f"homedir: {homedir}")
            remote_port = None
            identity = args.identity if (args.identity is not None) else f"{homedir}/.ssh/id_rsa"
            if (src_id is None):
                #result = subprocess.run(f"mkdir -p {src_path}", shell=True)
                remote_port = rj["dst_port"]
                remote_addr = rj["dst_addr"]
                cmd = f"sudo rsync -arz -v --progress --rsh=ssh -e 'sudo ssh -i {identity} -p {remote_port} -o StrictHostKeyChecking=no' {src_path} vastai_kaalia@{remote_addr}::{dst_id}/{dst_path}"
                print(cmd)
                result = subprocess.run(cmd, shell=True)
                #result = subprocess.run(["sudo", "rsync" "-arz", "-v", "--progress", "-rsh=ssh", "-e 'sudo ssh -i {homedir}/.ssh/id_rsa -p {remote_port} -o StrictHostKeyChecking=no'", src_path, "vastai_kaalia@{remote_addr}::{dst_id}"], shell=True)
            elif (dst_id is None):
                result = subprocess.run(f"mkdir -p {dst_path}", shell=True)
                remote_port = rj["src_port"]
                remote_addr = rj["src_addr"]
                cmd = f"sudo rsync -arz -v --progress --rsh=ssh -e 'sudo ssh -i {identity} -p {remote_port} -o StrictHostKeyChecking=no' vastai_kaalia@{remote_addr}::{src_id}/{src_path} {dst_path}"
                print(cmd)
                result = subprocess.run(cmd, shell=True)
                #result = subprocess.run(["sudo", "rsync" "-arz", "-v", "--progress", "-rsh=ssh", "-e 'sudo ssh -i {homedir}/.ssh/id_rsa -p {remote_port} -o StrictHostKeyChecking=no'", "vastai_kaalia@{remote_addr}::{src_id}", dst_path], shell=True)
        else:
            if (rj["success"]):
                print("Remote to Remote copy initiated - check instance status bar for progress updates (~30 seconds delayed).")
            else:
                if rj["msg"] == "src_path not supported VMs.":
                    print("copy between VM instances does not currently support subpaths (only full disk copy)")
                elif rj["msg"] == "dst_path not supported for VMs.":
                    print("copy between VM instances does not currently support subpaths (only full disk copy)")
                else:
                    print(rj["msg"])
    else:
        print(r.text)
        print("failed with error {r.status_code}".format(**locals()));


'''
@parser.command(
    argument("src", help="instance_id of source VM.", type=int),
    argument("dst", help="instance_id of destination VM", type=int),
    usage="vastai vm copy SRC DST",
    help=" Copy VM image from one VM instance to another",
    epilog=deindent("""
        Copies the entire VM image of from one instance to another.

        Note: destination VM must be stopped during copy. The source VM
        does not need to be stopped, but it's highly recommended that you keep
        the source VM stopped for the duration of the copy.
    """),
)
def vm__copy(args: argparse.Namespace):
    """
    Transfer VM image from one instance to another.

    @param src: instance_id of source.
    @param dst: instance_id of destination.
    """
    src_id = args.src
    dst_id = args.dst

    print(f"copying from {src_id} to {dst_id}")

    req_json = {
        "client_id": "me",
        "src_id": src_id,
        "dst_id": dst_id,
    }
    url = apiurl(args, f"/commands/copy_direct/")
    if (args.explain):
        print("request json: ")
        print(req_json)

    r = http_put(args, url,  headers=headers,json=req_json)
    r.raise_for_status()
    if (r.status_code == 200):
        rj = r.json();
        if (rj["success"]):
            print("Remote to Remote copy initiated - check instance status bar for progress updates (~30 seconds delayed).")
        else:
            if rj["msg"] == "Invalid src_path.":
                print("src instance is not a VM")
            elif rj["msg"] == "Invalid dst_path.":
                print("dst instance is not a VM")
            else:
                print(rj["msg"]);
    else:
        print(r.text);
        print("failed with error {r.status_code}".format(**locals()));
'''

@parser.command(
    argument("--src", help="path to source of object to copy", type=str),
    argument("--dst", help="path to target of copy operation", type=str, default="/workspace"),
    argument("--instance", help="id of the instance", type=str),
    argument("--connection", help="id of cloud connection on your account (get from calling 'vastai show connections')", type=str),
    argument("--transfer", help="type of transfer, possible options include Instance To Cloud and Cloud To Instance", type=str, default="Instance to Cloud"),
    argument("--dry-run", help="show what would have been transferred", action="store_true"),
    argument("--size-only", help="skip based on size only, not mod-time or checksum", action="store_true"),
    argument("--ignore-existing", help="skip all files that exist on destination", action="store_true"),
    argument("--update", help="skip files that are newer on the destination", action="store_true"),
    argument("--delete-excluded", help="delete files on dest excluded from transfer", action="store_true"),
    usage="vastai cloud copy --src SRC --dst DST --instance INSTANCE_ID -connection CONNECTION_ID --transfer TRANSFER_TYPE",
    help="Copy files/folders to and from cloud providers",
    epilog=deindent("""
        Copies a directory from a source location to a target location. Each of source and destination
        directories can be either local or remote, subject to appropriate read and write
        permissions required to carry out the action. The format for both src and dst is [instance_id:]path.
        You can find more information about the cloud copy operation here: https://vast.ai/docs/gpu-instances/cloud-sync
                    
        Examples:
         vastai show connections
         ID    NAME      Cloud Type
         1001  test_dir  drive 
         1003  data_dir  drive 
         
         vastai cloud_copy --src /folder --dst /workspace --instance 6003036 --connection 1001 --transfer "Instance To Cloud"

        The example copies all contents of /folder into /workspace on instance 6003036 from gdrive connection 'test_dir'.
    """),
)
def cloud__copy(args: argparse.Namespace):
    """
    Transfer data from one instance to another.

    @param src: Location of data object to be copied.
    @param dst: Target to copy object to.
    """

    url = apiurl(args, f"/commands/rclone/")
    #(src_id, src_path) = parse_vast_url(args.src)
    #(dst_id, dst_path) = parse_vast_url(args.dst)
    if (args.src is None) and (args.dst is None):
        print("invalid arguments")
        return

    # Initialize an empty list for flags
    flags = []

    # Append flags to the list based on the argparse.Namespace
    if args.dry_run:
        flags.append("--dry-run")
    if args.size_only:
        flags.append("--size-only")
    if args.ignore_existing:
        flags.append("--ignore-existing")
    if args.update:
        flags.append("--update")
    if args.delete_excluded:
        flags.append("--delete-excluded")

    print(f"copying {args.src} {args.dst} {args.instance} {args.connection} {args.transfer}")

    req_json = {
        "src": args.src,
        "dst": args.dst,
        "instance_id": args.instance,
        "selected": args.connection,
        "transfer": args.transfer,
        "flags": flags
    }

    if (args.explain):
        print("request json: ")
        print(req_json)
    
    r = http_post(args, url, headers=headers,json=req_json)
    r.raise_for_status()
    if (r.status_code == 200):
        print("Cloud Copy Started - check instance status bar for progress updates (~30 seconds delayed).")
        print("When the operation is finished you should see 'Cloud Cody Operation Finished' in the instance status bar.")  
    else:
        print(r.text);
        print("failed with error {r.status_code}".format(**locals()));


@parser.command(
    argument("--name", help="name of the api-key", type=str),
    argument("--permission_file", help="file path for json encoded permissions, see https://vast.ai/docs/cli/roles-and-permissions for more information", type=str),
    argument("--key_params", help="optional wildcard key params for advanced keys", type=str),
    usage="vastai create api-key --name NAME --permission_file PERMISSIONS",
    help="Create a new api-key with restricted permissions. Can be sent to other users and teammates",
    epilog=deindent("""
        In order to create api keys you must understand how permissions must be sent via json format. 
        You can find more information about permissions here: https://vast.ai/docs/cli/roles-and-permissions
    """)
)
def create__api_key(args):
    try:
        url = apiurl(args, "/auth/apikeys/")
        permissions = load_permissions_from_file(args.permission_file)
        r = http_post(args, url, headers=headers, json={"name": args.name, "permissions": permissions, "key_params": args.key_params})
        r.raise_for_status()
        print("api-key created {}".format(r.json()))
    except FileNotFoundError:
        print("Error: Permission file '{}' not found.".format(args.permission_file))
    except requests.exceptions.RequestException as e:
        print("Error: Failed to create api-key. Reason: {}".format(e))
    except Exception as e:
        print("An unexpected error occurred:", e)

@parser.command(
    argument("name", help="Environment variable name", type=str),
    argument("value", help="Environment variable value", type=str),
    usage="vastai create env-var <name> <value>",
    help="Create a new user environment variable",
)
def create__env_var(args):
    """Create a new environment variable for the current user."""
    url = apiurl(args, "/secrets/")
    data = {"key": args.name, "value": args.value}
    r = http_post(args, url, headers=headers, json=data)
    r.raise_for_status()

    result = r.json()
    if result.get("success"):
        print(result.get("msg", "Environment variable created successfully."))
    else:
        print(f"Failed to create environment variable: {result.get('msg', 'Unknown error')}")

@parser.command(
    argument("ssh_key", help="add the public key of your ssh key to your account (form the .pub file)", type=str),
    usage="vastai create ssh-key ssh_key",
    help="Create a new ssh-key",
    epilog=deindent("""
        Use this command to create a new ssh key for your account. 
        All ssh keys are stored in your account and can be used to connect to instances they've been added to
        All ssh keys should be added in rsa format
    """)
)
def create__ssh_key(args):
    url = apiurl(args, "/ssh/")
    r = http_post(args, url, headers=headers, json={"ssh_key": args.ssh_key})
    r.raise_for_status()
    print("ssh-key created {}".format(r.json()))

@parser.command(
    argument("--template_hash", help="template hash (required, but **Note**: if you use this field, you can skip search_params, as they are automatically inferred from the template)", type=str),
    argument("--template_id",   help="template id (optional)", type=int),
    argument("-n", "--no-default", action="store_true", help="Disable default search param query args"),
    argument("--launch_args",   help="launch args  string for create instance  ex: \"--onstart onstart_wget.sh  --env '-e ONSTART_PATH=https://s3.amazonaws.com/vast.ai/onstart_OOBA.sh' --image atinoda/text-generation-webui:default-nightly --disk 64\"", type=str),
    argument("--endpoint_name", help="deployment endpoint name (allows multiple autoscale groups to share same deployment endpoint)", type=str),
    argument("--endpoint_id",   help="deployment endpoint id (allows multiple autoscale groups to share same deployment endpoint)", type=int),
    argument("--test_workers",help="number of workers to create to get an performance estimate for while initializing autogroup (default 3)", type=int, default=3),
    argument("--gpu_ram",     help="estimated GPU RAM req  (independent of search string)", type=float),
    argument("--search_params", help="search param string for search offers    ex: \"gpu_ram>=23 num_gpus=2 gpu_name=RTX_4090 inet_down>200 direct_port_count>2 disk_space>=64\"", type=str),
    argument("--min_load", help="[NOTE: this field isn't currently used at the autojob level] minimum floor load in perf units/s  (token/s for LLms)", type=float),
    argument("--target_util", help="[NOTE: this field isn't currently used at the autojob level] target capacity utilization (fraction, max 1.0, default 0.9)", type=float),
    argument("--cold_mult",   help="[NOTE: this field isn't currently used at the autojob level]cold/stopped instance capacity target as multiple of hot capacity target (default 2.0)", type=float),
    usage="vastai autogroup create [OPTIONS]",
    help="Create a new autoscale group",
    epilog=deindent("""
        Create a new autoscaling group to manage a pool of worker instances.
                    
        Example: vastai create autogroup --template_hash HASH  --endpoint_name "LLama" --test_workers 5
        """),
)
def create__autogroup(args):
    url = apiurl(args, "/autojobs/" )

    # if args.launch_args_dict:
    #     launch_args_dict = json.loads(args.launch_args_dict)
    #     json_blob = {"client_id": "me", "min_load": args.min_load, "target_util": args.target_util, "cold_mult": args.cold_mult, "template_hash": args.template_hash, "template_id": args.template_id, "search_params": args.search_params, "launch_args_dict": launch_args_dict, "gpu_ram": args.gpu_ram, "endpoint_name": args.endpoint_name}
    if args.no_default:
        query = ""
    else:
        query = " verified=True rentable=True rented=False"
        #query = {"verified": {"eq": True}, "external": {"eq": False}, "rentable": {"eq": True}, "rented": {"eq": False}}
    search_params = (args.search_params if args.search_params is not None else "" + query).strip()

    json_blob = {"client_id": "me", "min_load": args.min_load, "target_util": args.target_util, "cold_mult": args.cold_mult, "test_workers" : args.test_workers, "template_hash": args.template_hash, "template_id": args.template_id, "search_params": search_params, "launch_args": args.launch_args, "gpu_ram": args.gpu_ram, "endpoint_name": args.endpoint_name, "endpoint_id": args.endpoint_id}
    
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_post(args, url, headers=headers,json=json_blob)
    r.raise_for_status()
    if 'application/json' in r.headers.get('Content-Type', ''):
        try:
            print("autogroup create {}".format(r.json()))
        except requests.exceptions.JSONDecodeError:
            print("The response is not valid JSON.")
            print(r)
            print(r.text)  # Print the raw response to help with debugging.
    else:
        print("The response is not JSON. Content-Type:", r.headers.get('Content-Type'))
        print(r.text)


@parser.command(
    argument("--min_load", help="minimum floor load in perf units/s  (token/s for LLms)", type=float, default=0.0),
    argument("--target_util", help="target capacity utilization (fraction, max 1.0, default 0.9)", type=float, default=0.9),
    argument("--cold_mult",   help="cold/stopped instance capacity target as multiple of hot capacity target (default 2.5)", type=float, default=2.5),
    argument("--cold_workers", help="min number of workers to keep 'cold' when you have no load (default 5)", type=int, default=5),
    argument("--max_workers", help="max number of workers your endpoint group can have (default 20)", type=int, default=20),
    argument("--endpoint_name", help="deployment endpoint name (allows multiple autoscale groups to share same deployment endpoint)", type=str),
    usage="vastai create endpoint [OPTIONS]",
    help="Create a new endpoint group",
    epilog=deindent("""
        Create a new endpoint group to manage many autoscaling groups
                    
        Example: vastai create endpoint --target_util 0.9 --cold_mult 2.0 --endpoint_name "LLama"
    """),
)
def create__endpoint(args):
    url = apiurl(args, "/endptjobs/" )

    json_blob = {"client_id": "me", "min_load": args.min_load, "target_util": args.target_util, "cold_mult": args.cold_mult, "cold_workers" : args.cold_workers, "max_workers" : args.max_workers, "endpoint_name": args.endpoint_name}
    
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = requests.post(url, headers=headers,json=json_blob)
    r.raise_for_status()
    if 'application/json' in r.headers.get('Content-Type', ''):
        try:
            print("create endpoint {}".format(r.json()))
        except requests.exceptions.JSONDecodeError:
            print("The response is not valid JSON.")
            print(r)
            print(r.text)  # Print the raw response to help with debugging.
    else:
        print("The response is not JSON. Content-Type:", r.headers.get('Content-Type'))
        print(r.text)

def get_runtype(args):
    runtype = 'ssh'
    if args.args:
        runtype = 'args'
    if (args.args == '') or (args.args == ['']) or (args.args == []):
        runtype = 'args'
        args.args = None
    if args.jupyter_dir or args.jupyter_lab:
        args.jupyter = True
    if args.jupyter and runtype == 'args':
        print("Error: Can't use --jupyter and --args together. Try --onstart or --onstart-cmd instead of --args.", file=sys.stderr)
        return 1

    if args.jupyter:
        runtype = 'jupyter_direc ssh_direc ssh_proxy' if args.direct else 'jupyter_proxy ssh_proxy'

    if args.ssh:
        runtype = 'ssh_direc ssh_proxy' if args.direct else 'ssh_proxy'

    return runtype


@parser.command(
    argument("id", help="id of instance type to launch (returned from search offers)", type=int),
    argument("--template_hash", help="Create instance from template info", type=str),
    argument("--user", help="User to use with docker create. This breaks some images, so only use this if you are certain you need it.", type=str),
    argument("--disk", help="size of local disk partition in GB", type=float, default=10),
    argument("--image", help="docker container image to launch", type=str),
    argument("--login", help="docker login arguments for private repo authentication, surround with '' ", type=str),
    argument("--label", help="label to set on the instance", type=str),
    argument("--onstart", help="filename to use as onstart script", type=str),
    argument("--onstart-cmd", help="contents of onstart script as single argument", type=str),
    argument("--entrypoint", help="override entrypoint for args launch instance", type=str),
    argument("--ssh",     help="Launch as an ssh instance type", action="store_true"),
    argument("--jupyter", help="Launch as a jupyter instance instead of an ssh instance", action="store_true"),
    argument("--direct",  help="Use (faster) direct connections for jupyter & ssh", action="store_true"),
    argument("--jupyter-dir", help="For runtype 'jupyter', directory in instance to use to launch jupyter. Defaults to image's working directory", type=str),
    argument("--jupyter-lab", help="For runtype 'jupyter', Launch instance with jupyter lab", action="store_true"),
    argument("--lang-utf8", help="Workaround for images with locale problems: install and generate locales before instance launch, and set locale to C.UTF-8", action="store_true"),
    argument("--python-utf8", help="Workaround for images with locale problems: set python's locale to C.UTF-8", action="store_true"),
    argument("--extra", help=argparse.SUPPRESS),
    argument("--env",   help="env variables and port mapping options, surround with '' ", type=str),
    argument("--args",  nargs=argparse.REMAINDER, help="list of arguments passed to container ENTRYPOINT. Onstart is recommended for this purpose. (must be last argument)"),
    #argument("--create-from", help="Existing instance id to use as basis for new instance. Instance configuration should usually be identical, as only the difference from the base image is copied.", type=str),
    argument("--force", help="Skip sanity checks when creating from an existing instance", action="store_true"),
    argument("--cancel-unavail", help="Return error if scheduling fails (rather than creating a stopped instance)", action="store_true"),
    argument("--bid_price", help="(OPTIONAL) create an INTERRUPTIBLE instance with per machine bid price in $/hour", type=float),
    usage="vastai create instance ID [OPTIONS] [--args ...]",
    help="Create a new instance",
    epilog=deindent("""
        Performs the same action as pressing the "RENT" button on the website at https://console.vast.ai/create/ 
        Creates an instance from an offer ID (which is returned from "search offers"). Each offer ID can only be used to create one instance.
        Besides the offer ID, you must pass in an '--image' argument as a minimum.

        If you use args/entrypoint launch mode, we create a container from your image as is, without attempting to inject ssh and or jupyter.
        If you use the args launch mode, you can override the entrypoint with --entrypoint, and pass arguments to the entrypoint with --args.
        If you use --args, that must be the last argument, as any following tokens are consumed into the args string.
        For ssh/jupyter launch types, use --onstart-cmd to pass in startup script, instead of --entrypoint and --args.
        
        Examples:

        # create an on-demand instance with the PyTorch (cuDNN Devel) template and 64GB of disk
        vastai create instance 384826 --template_hash 661d064bbda1f2a133816b6d55da07c3 --disk 64

        # create an on-demand instance with the pytorch/pytorch image, 40GB of disk, open 8081 udp, direct ssh, set hostname to billybob, and a small onstart script
        vastai create instance 6995713 --image pytorch/pytorch --disk 40 --env '-p 8081:8081/udp -h billybob' --ssh --direct --onstart-cmd "env | grep _ >> /etc/environment; echo 'starting up'";                

        # create an on-demand instance with the bobsrepo/pytorch:latest image, 20GB of disk, open 22, 8080, jupyter ssh, and set some env variables
        vastai create instance 384827  --image bobsrepo/pytorch:latest --login '-u bob -p 9d8df!fd89ufZ docker.io' --jupyter --direct --env '-e TZ=PDT -e XNAME=XX4 -p 22:22 -p 8080:8080' --disk 20

        # create an on-demand instance with the pytorch/pytorch image, 40GB of disk, override the entrypoint to bash and pass bash a simple command to keep the instance running. (args launch without ssh/jupyter)
        vastai create instance 5801802 --image pytorch/pytorch --disk 40 --onstart-cmd 'bash' --args -c 'echo hello; sleep infinity;'

        # create an interruptible (spot) instance with the PyTorch (cuDNN Devel) template, 64GB of disk, and a bid price of $0.10/hr
        vastai create instance 384826 --template_hash 661d064bbda1f2a133816b6d55da07c3 --disk 64 --bid_price 0.1

        Return value:
        Returns a json reporting the instance ID of the newly created instance:
        {'success': True, 'new_contract': 7835610} 
    """),
)
def create__instance(args: argparse.Namespace):
    """Performs the same action as pressing the "RENT" button on the website at https://console.vast.ai/create/.

    :param argparse.Namespace args: Namespace with many fields relevant to the endpoint.
    """

    if args.onstart:
        with open(args.onstart, "r") as reader:
            args.onstart_cmd = reader.read()
    if args.onstart_cmd is None:
        args.onstart_cmd = args.entrypoint

    runtype = None
    json_blob ={
        "client_id": "me",
        "image": args.image,
        "env" : parse_env(args.env),
        "price": args.bid_price,
        "disk": args.disk,
        "label": args.label,
        "extra": args.extra,
        "onstart": args.onstart_cmd,
        "image_login": args.login,
        "python_utf8": args.python_utf8,
        "lang_utf8": args.lang_utf8,
        "use_jupyter_lab": args.jupyter_lab,
        "jupyter_dir": args.jupyter_dir,
        #"create_from": args.create_from,
        "force": args.force,
        "cancel_unavail": args.cancel_unavail,
        "template_hash_id" : args.template_hash,
        "user": args.user
    }


    if args.template_hash is None:
        runtype = get_runtype(args)
        if runtype == 1:
            return 1
        json_blob["runtype"] = runtype

    if (args.args != None):
        json_blob["args"] = args.args

    #print(f"put asks/{args.id}/  runtype:{runtype}")
    url = apiurl(args, "/asks/{id}/".format(id=args.id))

    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, url,  headers=headers,json=json_blob)
    r.raise_for_status()
    if args.raw:
        return r
    else:
        print("Started. {}".format(r.json()))

@parser.command(
    argument("--email", help="email address to use for login", type=str),
    argument("--username", help="username to use for login", type=str),
    argument("--password", help="password to use for login", type=str),
    argument("--type", help="host/client", type=str),
    usage="vastai create subaccount --email EMAIL --username USERNAME --password PASSWORD --type TYPE",
    help="Create a subaccount",
    epilog=deindent("""
       Creates a new account that is considered a child of your current account as defined via the API key. 

       vastai create subaccount --email bob@gmail.com --username bob --password password --type host

       vastai create subaccount --email vast@gmail.com --username vast --password password --type host
    """),
)
def create__subaccount(args):
    """Creates a new account that is considered a child of your current account as defined via the API key.
    """
    # Default value for host_only, can adjust based on expected default behavior
    host_only = False
    
    # Only process the --account_type argument if it's provided
    if args.type:
        host_only = args.type.lower() == "host"

    json_blob = {
        "email": args.email,
        "username": args.username,
        "password": args.password,
        "host_only": host_only,
        "parent_id": "me"
    }

    # Use --explain to print the request JSON and return early
    if getattr(args, 'explain', False):
        print("Request JSON would be: ")
        print(json_blob)
        return  # Prevents execution of the actual API call

    # API call execution continues here if --explain is not used
    url = apiurl(args, "/users/")
    r = http_post(args, url, headers=headers, json=json_blob)
    r.raise_for_status()

    if r.status_code == 200:
        rj = r.json()
        print(rj)
    else:
        print(r.text)
        print(f"Failed with error {r.status_code}")

@parser.command(
    argument("--team_name", help="name of the team", type=str),
    usage="vastai create-team --team_name TEAM_NAME",
    help="Create a new team",
    epilog=deindent("""
        As of right now creating a team account will convert your current account into a team account. 
        Once you convert your user account into a team account, this change is permanent and cannot be reversed. 
        The created team account will inherit all aspects of your existing user account, including billing information, cloud services, and any other account settings.
        The user who initiates the team creation becomes the team owner. 
        Carefully evaluate the decision to convert your user account into a team account, as this change is permanent.
        For more information see: https://vast.ai/docs/team/introduction
    """)
)

def create__team(args):
    url = apiurl(args, "/team/")
    r = http_post(args, url, headers=headers, json={"team_name": args.team_name})
    r.raise_for_status()
    print(r.json())

@parser.command(
    argument("--name", help="name of the role", type=str),
    argument("--permissions", help="file path for json encoded permissions, look in the docs for more information", type=str),
    usage="vastai create team-role --name NAME --permissions PERMISSIONS",
    help="Add a new role to your team",
    epilog=deindent("""
        Creating a new team role involves understanding how permissions must be sent via json format.
        You can find more information about permissions here: https://vast.ai/docs/cli/roles-and-permissions
    """)
)
def create__team_role(args):
    url = apiurl(args, "/team/roles/")
    permissions = load_permissions_from_file(args.permissions)
    r = http_post(args, url, headers=headers, json={"name": args.name, "permissions": permissions})
    r.raise_for_status()
    print(r.json())

def get_template_arguments():
    return [
        argument("--name", help="name of the template", type=str),
        argument("--image", help="docker container image to launch", type=str),
        argument("--image_tag", help="docker image tag (can also be appended to end of image_path)", type=str),
        argument("--href", help="link you want to provide", type=str),
        argument("--repo", help="link to repository", type=str),
        argument("--login", help="docker login arguments for private repo authentication, surround with ''", type=str),
        argument("--env", help="Contents of the 'Docker options' field", type=str),
        argument("--ssh", help="Launch as an ssh instance type", action="store_true"),
        argument("--jupyter", help="Launch as a jupyter instance instead of an ssh instance", action="store_true"),
        argument("--direct", help="Use (faster) direct connections for jupyter & ssh", action="store_true"),
        argument("--jupyter-dir", help="For runtype 'jupyter', directory in instance to use to launch jupyter. Defaults to image's working directory", type=str),
        argument("--jupyter-lab", help="For runtype 'jupyter', Launch instance with jupyter lab", action="store_true"),
        argument("--onstart-cmd", help="contents of onstart script as single argument", type=str),
        argument("--search_params", help="search offers filters", type=str),
        argument("-n", "--no-default", action="store_true", help="Disable default search param query args"),
        argument("--disk_space", help="disk storage space, in GB", type=str),
        argument("--readme", help="readme string", type=str),
        argument("--hide-readme", help="hide the readme from users", action="store_true"),
        argument("--desc", help="description string", type=str),
        argument("--public", help="make template available to public", action="store_true"),
    ]

@parser.command(
    *get_template_arguments(),
    usage="vastai create template",
    help="Create a new template",
    epilog=deindent("""
        Create a template that can be used to create instances with

        Example: 
            vastai create template --name "tgi-llama2-7B-quantized" --image "ghcr.io/huggingface/text-generation-inference:1.0.3" 
                                    --env "-p 3000:3000 -e MODEL_ARGS='--model-id TheBloke/Llama-2-7B-chat-GPTQ --quantize gptq'" 
                                    --onstart-cmd 'wget -O - https://raw.githubusercontent.com/vast-ai/vast-pyworker/main/scripts/launch_tgi.sh | bash' 
                                    --search_params "gpu_ram>=23 num_gpus=1 gpu_name=RTX_3090 inet_down>128 direct_port_count>3 disk_space>=192 driver_version>=535086005 rented=False" 
                                    --disk_space 8.0 --ssh --direct
    """)
)
def create__template(args):
    # url = apiurl(args, f"/users/0/templates/")
    url = apiurl(args, f"/template/")
    jup_direct = args.jupyter and args.direct
    ssh_direct = args.ssh and args.direct
    use_ssh = args.ssh or args.jupyter
    runtype = "jupyter" if args.jupyter else ("ssh" if args.ssh else "args")
    if args.login:
        login = args.login.split(" ")
        docker_login_repo = login[0]
    else:
        docker_login_repo = None
    default_search_query = {}
    if not args.no_default:
        default_search_query = {"verified": {"eq": True}, "external": {"eq": False}, "rentable": {"eq": True}, "rented": {"eq": False}}
    
    extra_filters = parse_query(args.search_params, default_search_query, offers_fields, offers_alias, offers_mult)
    template = {
        "name" : args.name,
        "image" : args.image,
        "tag" : args.image_tag,
        "href": args.href,
        "repo" : args.repo,
        "env" : args.env, #str format
        "onstart" : args.onstart_cmd, #don't accept file name for now
        "jup_direct" : jup_direct,
        "ssh_direct" : ssh_direct,
        "use_jupyter_lab" : args.jupyter_lab,
        "runtype" : runtype,
        "use_ssh" : use_ssh,
        "jupyter_dir" : args.jupyter_dir,
        "docker_login_repo" : docker_login_repo, #can't store username/password with template for now
        "extra_filters" : extra_filters,
        "recommended_disk_space" : args.disk_space,
        "readme": args.readme,
        "readme_visible": not args.hide_readme,
        "desc": args.desc,
        "private": not args.public,
    }

    if (args.explain):
        print("request json: ")
        print(template)

    r = http_post(args, url, headers=headers, json=template)
    r.raise_for_status()
    try:
        rj = r.json()
        if rj["success"]:
            print(f"New Template: {rj['template']}")
        else:
            print(rj['msg'])
    except requests.exceptions.JSONDecodeError:
        print("The response is not valid JSON.")


@parser.command(
    argument("id", help="id of volume offer", type=int),
    argument("-s", "--size",
             help="size in GB of volume. Default 15 GB.", type=float),
    usage="vastai create volume ID [options]",
    help="Create a new volume",
    epilog=deindent("""
        Creates a volume from an offer ID (which is returned from "search volumes"). Each offer ID can be used to create multiple volumes,
        provided the size of all volumes does not exceed the size of the offer.
    """)
)
def create__volume(args: argparse.Namespace):
    
    size = args.size
    
    if not size:
        size = 15.0
    json_blob ={
        "size": size,
        "id": args.id
    }

    url = apiurl(args, "/volumes/")

    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, url,  headers=headers,json=json_blob)
    r.raise_for_status()
    if args.raw:
        return r
    else:
        print("Created. {}".format(r.json()))


@parser.command(
    argument("id", help="id of apikey to remove", type=int),
    usage="vastai delete api-key ID",
    help="Remove an api-key",
)
def delete__api_key(args):
    url = apiurl(args, "/auth/apikeys/{id}/".format(id=args.id))
    r = http_del(args, url, headers=headers)
    r.raise_for_status()
    print(r.json())

@parser.command(
    argument("id", help="id ssh key to delete", type=int),
    usage="vastai delete ssh-key ID",
    help="Remove an ssh-key",
)
def delete__ssh_key(args):
    url = apiurl(args, "/ssh/{id}/".format(id=args.id))
    r = http_del(args, url, headers=headers)
    r.raise_for_status()
    print(r.json())

@parser.command(
    argument("id", help="id of group to delete", type=int),
    usage="vastai delete autogroup ID ",
    help="Delete an autogroup group",
    epilog=deindent("""
        Note that deleteing an autogroup group doesn't automatically destroy all the instances that are associated with your autogroup group.
        Example: vastai delete autogroup 4242
    """),
)
def delete__autogroup(args):
    id  = args.id
    url = apiurl(args, f"/autojobs/{id}/" )
    json_blob = {"client_id": "me", "autojob_id": args.id}
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_del(args, url, headers=headers,json=json_blob)
    r.raise_for_status()
    if 'application/json' in r.headers.get('Content-Type', ''):
        try:
            print("autogroup delete {}".format(r.json()))
        except requests.exceptions.JSONDecodeError:
            print("The response is not valid JSON.")
            print(r)
            print(r.text)  # Print the raw response to help with debugging.
    else:
        print("The response is not JSON. Content-Type:", r.headers.get('Content-Type'))
        print(r.text)

@parser.command(
    argument("id", help="id of endpoint group to delete", type=int),
    usage="vastai delete endpoint ID ",
    help="Delete an endpoint group",
    epilog=deindent("""
        Note that deleting an endpoint group doesn't automatically destroy all the instances that are associated with your endpoint group, nor all the autogroups.
        Example: vastai delete endpoint 4242
    """),
)
def delete__endpoint(args):
    id  = args.id
    url = apiurl(args, f"/endptjobs/{id}/" )
    json_blob = {"client_id": "me", "endptjob_id": args.id}
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_del(args, url, headers=headers,json=json_blob)
    r.raise_for_status()
    if 'application/json' in r.headers.get('Content-Type', ''):
        try:
            print("delete endpoint {}".format(r.json()))
        except requests.exceptions.JSONDecodeError:
            print("The response is not valid JSON.")
            print(r)
            print(r.text)  # Print the raw response to help with debugging.
    else:
        print("The response is not JSON. Content-Type:", r.headers.get('Content-Type'))
        print(r.text)

@parser.command(
    argument("name", help="Environment variable name to delete", type=str),
    usage="vastai delete env-var <name>",
    help="Delete a user environment variable",
)
def delete__env_var(args):
    """Delete an environment variable for the current user."""
    url = apiurl(args, "/secrets/")
    data = {"key": args.name}
    r = http_del(args, url, headers=headers, json=data)
    r.raise_for_status()

    result = r.json()
    if result.get("success"):
        print(result.get("msg", "Environment variable deleted successfully."))
    else:
        print(f"Failed to delete environment variable: {result.get('msg', 'Unknown error')}")

@parser.command(
    argument("--template-id", help="Template ID of Template to Delete", type=int),
    argument("--hash-id", help="Hash ID of Template to Delete", type=str),
    usage="vastai delete template [--template-id <id> | --hash-id <hash_id>]",
    help="Delete a Template",
    epilog=deindent("""
        Note: Deleting a template only removes the user's replationship to a template. It does not get destroyed
        Example: vastai delete template --template-id 12345
        Example: vastai delete template --hash-id 49c538d097ad6437413b83711c9f61e8
    """),
)
def delete__template(args):
    url = apiurl(args, f"/template/" )
    
    if args.hash_id:
        json_blob = { "hash_id": args.hash_id }
    elif args.template_id:
        json_blob = { "template_id": args.template_id }
    else:
        print('ERROR: Must Specify either Template ID or Hash ID to delete a template')
        return
    
    if (args.explain):
        print("request json: ")
        print(json_blob)
        print(args)
        print(url)
    r = http_del(args, url, headers=headers,json=json_blob)
    print(r)
    # r.raise_for_status()
    if 'application/json' in r.headers.get('Content-Type', ''):
        try:
            print(r.json()['msg'])
        except requests.exceptions.JSONDecodeError:
            print("The response is not valid JSON.")
            print(r)
            print(r.text)  # Print the raw response to help with debugging.
    else:
        print("The response is not JSON. Content-Type:", r.headers.get('Content-Type'))
        print(r.text)


@parser.command(
    argument("id", help="id of volume contract", type=int),
    usage="vastai delete volume ID",
    help="Delete a volume",
    epilog=deindent("""
        Deletes volume with the given ID. All instances using the volume must be destroyed before the volume can be deleted.
    """)
)
def delete__volume(args: argparse.Namespace):
    url = apiurl(args, "/volumes/", query_args={"id": args.id})
    r = http_del(args, url, headers=headers)
    r.raise_for_status()
    if args.raw:
        return r
    else:
        print("Deleted. {}".format(r.json()))


def destroy_instance(id,args):
    url = apiurl(args, "/instances/{id}/".format(id=id))
    r = http_del(args, url, headers=headers,json={})
    r.raise_for_status()
    if args.raw:
        return r
    elif (r.status_code == 200):
        rj = r.json();
        if (rj["success"]):
            print("destroying instance {id}.".format(**(locals())));
        else:
            print(rj["msg"]);
    else:
        print(r.text);
        print("failed with error {r.status_code}".format(**locals()));


@parser.command(
    argument("id", help="id of instance to delete", type=int),
    usage="vastai destroy instance id [-h] [--api-key API_KEY] [--raw]",
    help="Destroy an instance (irreversible, deletes data)",
    epilog=deindent("""
        Perfoms the same action as pressing the "DESTROY" button on the website at https://console.vast.ai/instances/
        Example: vastai destroy instance 4242
    """),
)
def destroy__instance(args):
    """Perfoms the same action as pressing the "DESTROY" button on the website at https://console.vast.ai/instances/.

    :param argparse.Namespace args: should supply all the command-line options
    """
    destroy_instance(args.id,args)

@parser.command(
    argument("ids", help="ids of instance to destroy", type=int, nargs='+'),
    usage="vastai destroy instances [--raw] <id>",
    help="Destroy a list of instances (irreversible, deletes data)",
)
def destroy__instances(args):
    """
    """
    for id in args.ids:
        destroy_instance(id, args)

@parser.command(
    usage="vastai destroy team",
    help="Destroy your team",
)
def destroy__team(args):
    url = apiurl(args, "/team/")
    r = http_del(args, url, headers=headers)
    r.raise_for_status()
    print(r.json())

@parser.command(
    argument("instance_id", help="id of the instance", type=int),
    argument("ssh_key_id", help="id of the key to detach to the instance", type=str),
    usage="vastai detach instance_id ssh_key_id",
    help="Detach an ssh key from an instance",
    epilog=deindent("""
        Example: vastai detach 99999 12345
    """)
)
def detach__ssh(args):
    url = apiurl(args, "/instances/{id}/ssh/{ssh_key_id}/".format(id=args.instance_id, ssh_key_id=args.ssh_key_id))
    r = http_del(args, url, headers=headers)
    r.raise_for_status()
    print(r.json())

@parser.command(
    argument("id", help="id of instance to execute on", type=int),
    argument("COMMAND", help="bash command surrounded by single quotes",  type=str),
    usage="vastai execute id COMMAND",
    help="Execute a (constrained) remote command on a machine",
    epilog=deindent("""
        Examples:
          vastai execute 99999 'ls -l -o -r'
          vastai execute 99999 'rm -r home/delete_this.txt'
          vastai execute 99999 'du -d2 -h'

        available commands:
          ls                 List directory contents
          rm                 Remote files or directories
          du                 Summarize device usage for a set of files

        Return value:
        Returns the output of the command which was executed on the instance, if successful. May take a few seconds to retrieve the results.

    """),
)
def execute(args):
    """Execute a (constrained) remote command on a machine.
    :param argparse.Namespace args: should supply all the command-line options
    """
    url = apiurl(args, "/instances/command/{id}/".format(id=args.id))
    json_blob={"command": args.COMMAND} 
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, url,  headers=headers,json=json_blob )
    r.raise_for_status()

    if (r.status_code == 200):
        rj = r.json()
        if (rj["success"]):
            for i in range(0,30):
                time.sleep(0.3)
                url = rj.get("result_url",None)
                if (url is None):
                    api_key_id_h = hashlib.md5( (args.api_key + str(args.id)).encode('utf-8') ).hexdigest()
                    url = "https://s3.amazonaws.com/vast.ai/instance_logs/" + api_key_id_h + "C.log"
                # print(f"trying {url}")
                r = requests.get(url) #headers=headers
                # print(f"got: {r.status_code}")
                if (r.status_code == 200):
                    filtered_text = r.text.replace(rj["writeable_path"], '');
                    print(filtered_text)
                    break
        else:
            print(rj);
    else:
        print(r.text);
        print("failed with error {r.status_code}".format(**locals()));


@parser.command(
    argument("id", help="id of instance to execute on", type=int),
    argument("--level", help="log detail level (0 to 3)", type=int, default=1),
    usage="vastai get endpt-logs ID [--api-key API_KEY]",
    help="Fetch logs for a specific serverless endpoint group",
    epilog=deindent("""
        Example: vastai get endpt-logs 382
    """),
)
def get__endpt_logs(args):
    #url = apiurl(args, "/endptjobs/" )
    url = "https://run.vast.ai/get_endpoint_logs/"
    json_blob = {"id": args.id, "api_key": args.api_key}
    if (args.explain):
        print(f"{url} with request json: ")
        print(json_blob)

    #response = requests.post(f"{server_addr}/route/", headers={"Content-Type": "application/json"}, data=json.dumps(route_payload), timeout=4)
    #response.raise_for_status()  # Raises HTTPError for bad responses

    r = http_post(args, url, headers=headers,json=json_blob)
    r.raise_for_status()
    #print("autogroup list ".format(r.json()))
    levels = {0 : "info0", 1: "info1", 2: "trace", 3: "debug"}

    if (r.status_code == 200):
        rj = None
        try:
            rj = r.json()
        except Exception as e:
            print(str(e))
            print(r.text)
        if args.raw:
            # sort_keys
            return rj or r.text
        else:
            dbg_lvl = levels[args.level]
            print(rj[dbg_lvl])
            #print(json.dumps(rj, indent=1, sort_keys=True))
    else:
        print(r.text)


@parser.command(
    argument("--email", help="email of user to be invited", type=str),
    argument("--role", help="role of user to be invited", type=str),
    usage="vastai invite member --email EMAIL --role ROLE",
    help="Invite a team member",
)
def invite__member(args):
    url = apiurl(args, "/team/invite/", query_args={"email": args.email, "role": args.role})
    r = http_post(args, url, headers=headers)
    r.raise_for_status()
    if (r.status_code == 200):
        print(f"successfully invited {args.email} to your current team")
    else:
        print(r.text);
        print(f"failed with error {r.status_code}")


@parser.command(
    argument("id", help="id of instance to label", type=int),
    argument("label", help="label to set", type=str),
    usage="vastai label instance <id> <label>",
    help="Assign a string label to an instance",
)
def label__instance(args):
    """

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    url       = apiurl(args, "/instances/{id}/".format(id=args.id))
    json_blob = { "label": args.label }
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, url,  headers=headers,json=json_blob)
    r.raise_for_status()

    rj = r.json();
    if rj["success"]:
        print("label for {args.id} set to {args.label}.".format(**(locals())));
    else:
        print(rj["msg"]);


def fetch_url_content(url):
    response = requests.get(url)
    response.raise_for_status()  # Raises an HTTPError for bad responses
    return response.text


def _get_gpu_names() -> List[str]:
    """Returns a set of GPU names available on Vast.ai, with results cached for 24 hours."""
    
    def is_cache_valid() -> bool:
        """Checks if the cache file exists and is less than 24 hours old."""
        if not os.path.exists(CACHE_FILE):
            return False
        cache_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
        return cache_age < CACHE_DURATION
    
    if is_cache_valid():
        with open(CACHE_FILE, "r") as file:
            gpu_names = json.load(file)
    else:
        endpoint = "/api/v0/gpu_names/unique/"
        url = f"{server_url_default}{endpoint}"
        r = requests.get(url, headers={})
        r.raise_for_status()  # Will raise an exception for HTTP errors
        gpu_names = r.json()
        with open(CACHE_FILE, "w") as file:
            json.dump(gpu_names, file)

    formatted_gpu_names = [
        name.replace(" ", "_").replace("-", "_") for name in gpu_names['gpu_names']
    ]
    return formatted_gpu_names


REGIONS = {
    "North_America": "[US, CA]",
    "South_America": "[BR, AR, CL]",
    "Europe": "[SE, UA, GB, PL, PT, SI, DE, IT, CH, LT, GR, FI, IS, AT, FR, RO, MD, HU, NO, MK, BG, ES, HR, NL, CZ, EE",
    "Asia": "[CN, JP, KR, ID, IN, HK, MY, IL, TH, QA, TR, RU, VN, TW, OM, SG, AE, KZ]",
    "Oceania": "[AU, NZ]",
    "Africa": "[EG, ZA]",
}

def _is_valid_region(region):
    """region is valid if it is a key in REGIONS or a string list of country codes."""
    if region in REGIONS:
        return True
    if region.startswith("[") and region.endswith("]"):
        country_codes = region[1:-1].split(',')
        return all(len(code.strip()) == 2 for code in country_codes)
    return False

def _parse_region(region):
    """Returns a string in a list format of two-char country codes."""
    if region in REGIONS:
        return REGIONS[region]
    return region

@parser.command(
    argument("-g", "--gpu-name", type=str, required=True, choices=_get_gpu_names(), help="Name of the GPU model, replace spaces with underscores"),
    argument("-n", "--num-gpus", type=str, required=True, choices=["1", "2", "4", "8", "12", "14"], help="Number of GPUs required"),
    argument("-r", "--region", type=str, help="Geographical location of the instance"),
    argument("-i", "--image", required=True, help="Name of the image to use for instance"),
    argument("-d", "--disk", type=float, default=16.0, help="Disk space required in GB"),
    argument("--limit", default=3, type=int, help=""),
    argument("-o", "--order", type=str, help="Comma-separated list of fields to sort on. postfix field with - to sort desc. ex: -o 'num_gpus,total_flops-'.  default='score-'", default='score-'),
    argument("--login", help="docker login arguments for private repo authentication, surround with '' ", type=str),
    argument("--label", help="label to set on the instance", type=str),
    argument("--onstart", help="filename to use as onstart script", type=str),
    argument("--onstart-cmd", help="contents of onstart script as single argument", type=str),
    argument("--entrypoint", help="override entrypoint for args launch instance", type=str),
    argument("--ssh",     help="Launch as an ssh instance type", action="store_true"),
    argument("--jupyter", help="Launch as a jupyter instance instead of an ssh instance", action="store_true"),
    argument("--direct",  help="Use (faster) direct connections for jupyter & ssh", action="store_true"),
    argument("--jupyter-dir", help="For runtype 'jupyter', directory in instance to use to launch jupyter. Defaults to image's working directory", type=str),
    argument("--jupyter-lab", help="For runtype 'jupyter', Launch instance with jupyter lab", action="store_true"),
    argument("--lang-utf8", help="Workaround for images with locale problems: install and generate locales before instance launch, and set locale to C.UTF-8", action="store_true"),
    argument("--python-utf8", help="Workaround for images with locale problems: set python's locale to C.UTF-8", action="store_true"),
    argument("--extra", help=argparse.SUPPRESS),
    argument("--env",   help="env variables and port mapping options, surround with '' ", type=str),
    argument("--args",  nargs=argparse.REMAINDER, help="list of arguments passed to container ENTRYPOINT. Onstart is recommended for this purpose. (must be last argument)"),
    argument("--force", help="Skip sanity checks when creating from an existing instance", action="store_true"),
    argument("--cancel-unavail", help="Return error if scheduling fails (rather than creating a stopped instance)", action="store_true"),
    argument("--template_hash",   help="template hash which contains all relevant information about an instance. This can be used as a replacement for other parameters describing the instance configuration", type=str),
    usage="vastai launch instance [--help] [--api-key API_KEY] <gpu_name> <num_gpus> <image> [geolocation] [disk_space]",
    help="Launch the top instance from the search offers based on the given parameters",
    epilog=deindent("""
        Launches an instance based on the given parameters. The instance will be created with the top offer from the search results.
        Besides the gpu_name and num_gpus, you must pass in an '--image' argument as a minimum.

        If you use args/entrypoint launch mode, we create a container from your image as is, without attempting to inject ssh and or jupyter.
        If you use the args launch mode, you can override the entrypoint with --entrypoint, and pass arguments to the entrypoint with --args.
        If you use --args, that must be the last argument, as any following tokens are consumed into the args string.
        For ssh/jupyter launch types, use --onstart-cmd to pass in startup script, instead of --entrypoint and --args.
                    
        Examples:

            # launch a single RTX 3090 instance with the pytorch image and 16 GB of disk space located anywhere
            python vast.py launch instance -g RTX_3090 -n 1 -i pytorch/pytorch
                    
            # launch a 4x RTX 3090 instance with the pytorch image and 32 GB of disk space located in North America
            python vast.py launch instance -g RTX_3090 -n 4 -i pytorch/pytorch -d 32.0 -r North_America
            
        Available fields:

            Name                    Type      Description

            num_gpus:               int       # of GPUs
            gpu_name:               string    GPU model name
            region:                 string    Region of the instance
            image:                  string    Docker image name
            disk_space:             float     Disk space in GB
            ssh, jupyter, direct:   bool      Flags to specify the instance type and connection method.
            env:                    str       Environment variables and port mappings, encapsulated in single quotes.
            args:                   list      Arguments passed to the container's ENTRYPOINT, used only if '--args' is specified.
    """),
)
def launch__instance(args):
    """Allows for a more streamlined and simplified way to create an instance.

    :param argparse.Namespace args: Namespace with many fields relevant to the endpoint.
    """
    args_query = f"num_gpus={args.num_gpus} gpu_name={args.gpu_name}"

    if args.region:
        if not _is_valid_region(args.region):
            print("Invalid region or country codes provided.")
            return
        region_query = _parse_region(args.region)
        args_query += f" geolocation in {region_query}"

    if args.disk:
        args_query += f" disk_space>={args.disk}"

    base_query = {"verified": {"eq": True}, "external": {"eq": False}, "rentable": {"eq": True}, "rented": {"eq": False}}
    query = parse_query(args_query, base_query, offers_fields, offers_alias, offers_mult)

    order = []
    for name in args.order.split(","):
        name = name.strip()
        if not name: continue
        direction = "asc"
        field = name
        if name.strip("-") != name:
            direction = "desc"
            field = name.strip("-")
        if name.strip("+") != name:
            direction = "asc"
            field = name.strip("+")
        #print(f"{field} {name} {direction}")
        if field in offers_alias:
            field = offers_alias[field];
        order.append([field, direction])
    query["order"] = order
    query["type"] = "on-demand"
    # For backwards compatibility, support --type=interruptible option
    if query["type"] == 'interruptible':
        query["type"] = 'bid'
    if (args.limit):
        query["limit"] = int(args.limit)
    query["allocated_storage"] = args.disk

    if args.onstart:
        with open(args.onstart, "r") as reader:
            args.onstart_cmd = reader.read()

    if args.onstart_cmd is None:
        args.onstart_cmd = args.entrypoint

    json_blob = {
        "client_id": "me", 
        "gpu_name": args.gpu_name, 
        "num_gpus": args.num_gpus, 
        "region": args.region, 
        "image": args.image, 
        "disk": args.disk,  
        "q" : query,
        "env" : parse_env(args.env),
        "disk": args.disk,
        "label": args.label,
        "extra": args.extra,
        "onstart": args.onstart_cmd,
        "image_login": args.login,
        "python_utf8": args.python_utf8,
        "lang_utf8": args.lang_utf8,
        "use_jupyter_lab": args.jupyter_lab,
        "jupyter_dir": args.jupyter_dir,
        "force": args.force,
        "cancel_unavail": args.cancel_unavail,
        "template_hash_id" : args.template_hash
    }
    # don't send runtype with template_hash
    if args.template_hash is None:
        runtype = get_runtype(args)
        if runtype == 1:
            return 1
        json_blob["runtype"] = runtype

    if (args.args != None):
        json_blob["args"] = args.args

    url = apiurl(args, "/launch_instance/".format())

    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, url, headers=headers, json=json_blob)
    try:
        r.raise_for_status()  # This will raise an exception for HTTP error codes
        response_data = r.json()
        if args.raw:
            return r
        else:
            print("Started. {}".format(r.json()))
        if response_data.get('success'):
            print(f"Instance launched successfully: {response_data.get('new_contract')}")
        else:
            print(f"Failed to launch instance: {response_data.get('error')}, {response_data.get('message')}")
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err}")
    except Exception as err:
        print(f"An error occurred: {err}")


@parser.command(
    argument("INSTANCE_ID", help="id of instance", type=int),
    argument("--tail", help="Number of lines to show from the end of the logs (default '1000')", type=str),
    argument("--filter", help="Grep filter for log entries", type=str),
    argument("--daemon-logs", help="Fetch daemon system logs instead of container logs", action="store_true"),
    usage="vastai logs INSTANCE_ID [OPTIONS] ",
    help="Get the logs for an instance",
)
def logs(args):
    """Get the logs for an instance
    :param argparse.Namespace args: should supply all the command-line options
    """
    url = apiurl(args, "/instances/request_logs/{id}/".format(id=args.INSTANCE_ID))
    json_blob = {'filter': args.filter} if args.filter else {}
    if args.tail:
        json_blob.update({'tail': args.tail})
    if args.daemon_logs:
        json_blob.update({'daemon_logs': 'true'})
    if args.explain:
        print("request json: ")
        print(json_blob)

    r = http_put(args, url, headers=headers, json=json_blob)
    r.raise_for_status()

    if r.status_code == 200:
        rj = r.json()
        for i in range(0, 30):
            time.sleep(0.3)
            api_key_id_h = hashlib.md5((args.api_key + str(args.INSTANCE_ID)).encode('utf-8')).hexdigest()
            url = "https://s3.amazonaws.com/vast.ai/instance_logs/" + api_key_id_h + ".log"
            print(f"waiting on logs for instance {args.INSTANCE_ID} fetching from {url}")
            r = requests.get(url)
            if r.status_code == 200:
                result = r.text
                cleaned_text = re.sub(r'\n\s*\n', '\n', result)
                print(cleaned_text)
                break
        else:
            print(rj["msg"])
    else:
        print(r.text)
        print(f"failed with error {r.status_code}")



@parser.command(
    argument("id", help="id of instance to prepay for", type=int),
    argument("amount", help="amount of instance credit prepayment (default discount func of 0.2 for 1 month, 0.3 for 3 months)", type=float),
    usage="vastai prepay instance ID AMOUNT",
    help="Deposit credits into reserved instance",
)
def prepay__instance(args):
    """
    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    url       = apiurl(args, "/instances/prepay/{id}/".format(id=args.id))
    json_blob = { "amount": args.amount }
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, url,  headers=headers,json=json_blob)
    r.raise_for_status()

    rj = r.json();
    if rj["success"]:
        timescale = round( rj["timescale"], 3)
        discount_rate = 100.0*round( rj["discount_rate"], 3)
        print("prepaid for {timescale} months of instance {args.id} applying ${args.amount} credits for a discount of {discount_rate}%".format(**(locals())));
    else:
        print(rj["msg"]);

'''
'''


@parser.command(
    argument("id", help="id of instance to reboot", type=int),
    usage="vastai reboot instance ID [OPTIONS]",
    help="Reboot (stop/start) an instance",
    epilog=deindent("""
        Stops and starts container without any risk of losing GPU priority.
    """),
)
def reboot__instance(args):
    """
    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    url = apiurl(args, "/instances/reboot/{id}/".format(id=args.id))
    r = http_put(args, url,  headers=headers,json={})
    r.raise_for_status()

    if (r.status_code == 200):
        rj = r.json();
        if (rj["success"]):
            print("Rebooting instance {args.id}.".format(**(locals())));
        else:
            print(rj["msg"]);
    else:
        print(r.text);
        print("failed with error {r.status_code}".format(**locals()));


@parser.command(
    argument("id", help="id of instance to reboot", type=int),
    usage="vastai recycle instance ID [OPTIONS]",
    help="Recycle (destroy/create) an instance",
    epilog=deindent("""
        Destroys and recreates container in place (from newly pulled image) without any risk of losing GPU priority.
    """),
)
def recycle__instance(args):
    """
    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    url = apiurl(args, "/instances/recycle/{id}/".format(id=args.id))
    r = http_put(args, url,  headers=headers,json={})
    r.raise_for_status()

    if (r.status_code == 200):
        rj = r.json()
        if (rj["success"]):
            print("Recycling instance {args.id}.".format(**(locals())));
        else:
            print(rj["msg"]);
    else:
        print(r.text)
        print("failed with error {r.status_code}".format(**locals()));

@parser.command(
    argument("id", help="id of user to remove", type=int),
    usage="vastai remove member ID",
    help="Remove a team member",
)
def remove__member(args):
    url = apiurl(args, "/team/members/{id}/".format(id=args.id))
    r = http_del(args, url, headers=headers)
    r.raise_for_status()
    print(r.json())

@parser.command(
    argument("NAME", help="name of the role", type=str),
    usage="vastai remove team-role NAME",
    help="Remove a role from your team",
)
def remove__team_role(args):
    url = apiurl(args, "/team/roles/{id}/".format(id=args.NAME))
    r = http_del(args, url, headers=headers)
    r.raise_for_status()
    print(r.json())

@parser.command(
    argument("id", help="machine id", type=int),
    usage="vastai reports ID",
    help="Get the user reports for a given machine",
)
def reports(args):
    """
    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    url = apiurl(args, "/machines/{id}/reports/".format(id=args.id))
    json_blob = {"machine_id" : args.id}

    if (args.explain):
        print("request json: ")
        print(json_blob)
    
    r = requests.get(url, headers=headers, json=json_blob)
    r.raise_for_status()

    if (r.status_code == 200):
        print(f"reports: {json.dumps(r.json(), indent=2)}")


@parser.command(
    usage="vastai reset api-key",
    help="Reset your api-key (get new key from website)",
)
def reset__api_key(args):
    """Caution: a bad API key will make it impossible to connect to the servers.
    """
    print('fml')
    #url = apiurl(args, "/users/current/reset-apikey/", {"owner": "me"})
    url = apiurl(args, "/commands/reset_apikey/" )
    json_blob = {"client_id": "me",}
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, url,  headers=headers,json=json_blob)
    r.raise_for_status()
    print("api-key reset ".format(r.json()))


def exec_with_threads(f, args, nt=16, max_retries=5):
    def worker(sub_args):
        for arg in sub_args:
            retries = 0
            while retries <= max_retries:
                try:
                    result = None
                    if isinstance(arg,tuple):
                        result = f(*arg)
                    else:
                        result = f(arg)
                    if result:  # Assuming a truthy return value means success
                        break
                except Exception as e:
                    print(str(e))
                    pass
                retries += 1
                stime = 0.25 * 1.3 ** retries
                print(f"retrying in {stime}s")
                time.sleep(stime)  # Exponential backoff

    # Split args into nt sublists
    args_per_thread = math.ceil(len(args) / nt)
    sublists = [args[i:i + args_per_thread] for i in range(0, len(args), args_per_thread)]

    with ThreadPoolExecutor(max_workers=nt) as executor:
        executor.map(worker, sublists)


def split_into_sublists(lst, k):
    # Calculate the size of each sublist
    sublist_size = (len(lst) + k - 1) // k
    
    # Create the sublists using list comprehension
    sublists = [lst[i:i + sublist_size] for i in range(0, len(lst), sublist_size)]
    
    return sublists


def split_list(lst, k):
    """
    Splits a list into sublists of maximum size k.
    """
    return [lst[i:i + k] for i in range(0, len(lst), k)]


def start_instance(id,args):

    json_blob ={"state": "running"}
    if isinstance(id,list):
        url = apiurl(args, "/instances/")
        json_blob["ids"] = id
    else:
        url = apiurl(args, "/instances/{id}/".format(id=id))

    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, url,  headers=headers,json=json_blob)
    r.raise_for_status()

    if (r.status_code == 200):
        rj = r.json()
        if (rj["success"]):
            print("starting instance {id}.".format(**(locals())))
        else:
            print(rj["msg"])
        return True
    else:
        print(r.text)
        print("failed with error {r.status_code}".format(**locals()))
    return False

@parser.command(
    argument("id", help="ID of instance to start/restart", type=int),
    usage="vastai start instance ID [OPTIONS]",
    help="Start a stopped instance",
    epilog=deindent("""
        This command attempts to bring an instance from the "stopped" state into the "running" state. This is subject to resource availability on the machine that the instance is located on.
        If your instance is stuck in the "scheduling" state for more than 30 seconds after running this, it likely means that the required resources on the machine to run your instance are currently unavailable.
        Examples: 
            vastai start instances $(vastai show instances -q)
            vastai start instance 329838
    """),
)
def start__instance(args):
    """

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    start_instance(args.id,args)


@parser.command(
    argument("ids", help="ids of instance to start", type=int, nargs='+'),
    usage="vastai start instances [OPTIONS] ID0 ID1 ID2...",
    help="Start a list of instances",
)
def start__instances(args):
    """
    for id in args.IDs:
        start_instance(id, args)
    """

    #start_instance(args.IDs, args)
    #exec_with_threads(lambda id : start_instance(id, args), args.IDs)

    idlist = split_list(args.ids, 64)
    exec_with_threads(lambda ids : start_instance(ids, args), idlist, nt=8)



def stop_instance(id,args):

    json_blob ={"state": "stopped"}
    if isinstance(id,list):
        url = apiurl(args, "/instances/")
        json_blob["ids"] = id
    else:
        url = apiurl(args, "/instances/{id}/".format(id=id))

    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, url,  headers=headers,json=json_blob)
    r.raise_for_status()

    if (r.status_code == 200):
        rj = r.json()
        if (rj["success"]):
            print("stopping instance {id}.".format(**(locals())))
        else:
            print(rj["msg"])
        return True
    else:
        print(r.text)
        print("failed with error {r.status_code}".format(**locals()))
    return False


@parser.command(
    argument("id", help="id of instance to stop", type=int),
    usage="vastai stop instance ID [OPTIONS]",
    help="Stop a running instance",
    epilog=deindent("""
        This command brings an instance from the "running" state into the "stopped" state. When an instance is "stopped" all of your data on the instance is preserved, 
        and you can resume use of your instance by starting it again. Once stopped, starting an instance is subject to resource availability on the machine that the instance is located on.
        There are ways to move data off of a stopped instance, which are described here: https://vast.ai/docs/gpu-instances/data-movement
    """)
)
def stop__instance(args):
    """

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    stop_instance(args.id,args)

@parser.command(
    argument("ids", help="ids of instance to stop", type=int, nargs='+'),
    usage="vastai stop instances [OPTIONS] ID0 ID1 ID2...",
    help="Stop a list of instances",
    epilog=deindent("""
        Examples: 
            vastai stop instances $(vastai show instances -q)
            vastai stop instances 329838 984849
    """),
)
def stop__instances(args):
    """
    for id in args.IDs:
        stop_instance(id, args)
    """

    idlist = split_list(args.ids, 64)
    #stop_instance(args.IDs, args)
    exec_with_threads(lambda ids : stop_instance(ids, args), idlist, nt=8)



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

@parser.command(
    argument("query", help="Search query in simple query syntax (see below)", nargs="*", default=None),
    usage="vastai search benchmarks [--help] [--api-key API_KEY] [--raw] <query>",
    help="Search for benchmark results using custom query",
    epilog=deindent("""
        Query syntax:

            query = comparison comparison...
            comparison = field op value
            field = <name of a field>
            op = one of: <, <=, ==, !=, >=, >, in, notin
            value = <bool, int, float, string> | 'any' | [value0, value1, ...]
            bool: True, False

        note: to pass '>' and '<' on the command line, make sure to use quotes
        note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'

        Examples:

            # search for benchmarks with score > 100 for llama2_70B model on 2 specific machines
            vastai search benchmarks 'score > 100.0  model=llama2_70B  machine_id in [302,402]'

        Available fields:

              Name                  Type       Description

            contract_id             int        ID of instance/contract reporting benchmark
            id                      int        benchmark unique ID
            image                   string     image used for benchmark
            last_update             float      date of benchmark
            machine_id              int        id of machine benchmarked
            model                   string     name of model used in benchmark
            name                    string     name of benchmark
            num_gpus                int        number of gpus used in benchmark
            score                   float      benchmark score result
    """),
    aliases=hidden_aliases(["search benchmarks"]),
)
def search__benchmarks(args):
    """Creates a query based on search parameters as in the examples above.
    :param argparse.Namespace args: should supply all the command-line options
    """
    try:
        query = {}
        if args.query is not None:
            query = parse_query(args.query, query, benchmarks_fields)
            query = fix_date_fields(query, ['last_update'])

    except ValueError as e:
        print("Error: ", e)
        return 1  
    #url = apiurl(args, "/benchmarks", {"select_cols" : ['id','last_update','machine_id','score'], "select_filters" : query})
    url = apiurl(args, "/benchmarks", {"select_cols" : ['*'], "select_filters" : query})
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    rows = r.json()
    if True: # args.raw:
        return rows
    else:
        display_table(rows, displayable_fields)



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

@parser.command(
    argument("query", help="Search query in simple query syntax (see below)", nargs="*", default=None),
    usage="vastai search invoices [--help] [--api-key API_KEY] [--raw] <query>",
    help="Search for benchmark results using custom query",
    epilog=deindent("""
        Query syntax:

            query = comparison comparison...
            comparison = field op value
            field = <name of a field>
            op = one of: <, <=, ==, !=, >=, >, in, notin
            value = <bool, int, float, string> | 'any' | [value0, value1, ...]
            bool: True, False

        note: to pass '>' and '<' on the command line, make sure to use quotes
        note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'

        Examples:

            # search for somewhat reliable single RTX 3090 instances, filter out any duplicates or offers that conflict with our existing stopped instances
            vastai search invoices 'amount_cents>3000  '

        Available fields:

      Name                  Type       Description

    id                  int,            
    user_id             int,            
    when                float,          utc epoch timestamp of initial invoice creation
    paid_on             float,          actual payment date (utc epoch timestamp )
    payment_expected    float,          expected payment date (utc epoch timestamp )
    amount_cents        int,            amount of payment in cents
    is_credit           bool,           is a credit purchase
    is_delayed          bool,           is not yet paid
    balance_before      float,          balance before
    balance_after       float,          balance after
    original_amount     int,            original amount of payment
    event_id            string,           
    cut_amount          int,               
    cut_percent         float,            
    extra               json,           
    service             string,         type of payment 
    stripe_charge       json,           
    stripe_refund       json,           
    stripe_payout       json,           
    error               json,           
    paypal_email        string,         email for paypal/wise payments
    transfer_group      string,         
    failed              bool,                   
    refunded            bool,                   
    is_check            bool,                   
    """),
    aliases=hidden_aliases(["search invoices"]),
)
def search__invoices(args):
    """Creates a query based on search parameters as in the examples above.
    :param argparse.Namespace args: should supply all the command-line options
    """
    try:
        query = {}
        if args.query is not None:
            query = parse_query(args.query, query, invoices_fields)
            query = fix_date_fields(query, ['when', 'paid_on', 'payment_expected', 'balance_before', 'balance_after'])

    except ValueError as e:
        print("Error: ", e)
        return 1  
    url = apiurl(args, "/invoices", {"select_cols" : ['*'], "select_filters" : query})
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    rows = r.json()
    if True: # args.raw:
        return rows
    else:
        display_table(rows, displayable_fields)


@parser.command(
    argument("-t", "--type", default="on-demand", help="Show 'on-demand', 'reserved', or 'bid'(interruptible) pricing. default: on-demand"),
    argument("-i", "--interruptible", dest="type", const="bid", action="store_const", help="Alias for --type=bid"),
    argument("-b", "--bid", dest="type", const="bid", action="store_const", help="Alias for --type=bid"),
    argument("-r", "--reserved", dest="type", const="reserved", action="store_const", help="Alias for --type=reserved"),
    argument("-d", "--on-demand", dest="type", const="on-demand", action="store_const", help="Alias for --type=on-demand"),
    argument("-n", "--no-default", action="store_true", help="Disable default query"),
    argument("--new", action="store_true", help="New search exp"),
    argument("--limit", type=int, help=""),
    argument("--disable-bundling", action="store_true", help="Deprecated"),
    argument("--storage", type=float, default=5.0, help="Amount of storage to use for pricing, in GiB. default=5.0GiB"),
    argument("-o", "--order", type=str, help="Comma-separated list of fields to sort on. postfix field with - to sort desc. ex: -o 'num_gpus,total_flops-'.  default='score-'", default='score-'),
    argument("query", help="Query to search for. default: 'external=false rentable=true verified=true', pass -n to ignore default", nargs="*", default=None),
    usage="vastai search offers [--help] [--api-key API_KEY] [--raw] <query>",
    help="Search for instance types using custom query",
    epilog=deindent("""
        Query syntax:

            query = comparison comparison...
            comparison = field op value
            field = <name of a field>
            op = one of: <, <=, ==, !=, >=, >, in, notin
            value = <bool, int, float, string> | 'any' | [value0, value1, ...]
            bool: True, False

        note: to pass '>' and '<' on the command line, make sure to use quotes
        note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'

        Examples:

            # search for somewhat reliable single RTX 3090 instances, filter out any duplicates or offers that conflict with our existing stopped instances
            vastai search offers 'reliability > 0.98 num_gpus=1 gpu_name=RTX_3090 rented=False'

            # search for datacenter gpus with minimal compute_cap and total_flops
            vastai search offers 'compute_cap > 610 total_flops > 5 datacenter=True'

            # search for reliable 4 gpu offers in Taiwan or Sweden
            vastai search offers 'reliability>0.99 num_gpus=4 geolocation in [TW,SE]'

            # search for reliable RTX 3090 or 4090 gpus NOT in China or Vietnam
            vastai search offers 'reliability>0.99 gpu_name in ["RTX 4090", "RTX 3090"] geolocation notin [CN,VN]'

            # search for machines with nvidia drivers 535.86.05 or greater (and various other options)
            vastai search offers 'disk_space>146 duration>24 gpu_ram>10 cuda_vers>=12.1 direct_port_count>=2 driver_version >= 535.86.05'

            # search for reliable machines with at least 4 gpus, unverified, order by num_gpus, allow conflicts
            vastai search offers 'reliability > 0.99  num_gpus>=4 verified=False rented=any' -o 'num_gpus-'

            # search for arm64 cpu architecture
            vastai search offers 'cpu_arch=arm64'
            
        Available fields:

              Name                  Type       Description

            bw_nvlink               float     bandwidth NVLink
            compute_cap:            int       cuda compute capability*100  (ie:  650 for 6.5, 700 for 7.0)
            cpu_arch                string    host machine cpu architecture (e.g. amd64, arm64)
            cpu_cores:              int       # virtual cpus
            cpu_ghz:                Float     # cpu clock speed GHZ
            cpu_cores_effective:    float     # virtual cpus you get
            cpu_ram:                float     system RAM in gigabytes
            cuda_vers:              float     machine max supported cuda version (based on driver version)
            datacenter:             bool      show only datacenter offers
            direct_port_count       int       open ports on host's router
            disk_bw:                float     disk read bandwidth, in MB/s
            disk_space:             float     disk storage space, in GB
            dlperf:                 float     DL-perf score  (see FAQ for explanation)
            dlperf_usd:             float     DL-perf/$
            dph:                    float     $/hour rental cost
            driver_version:         string    machine's nvidia/amd driver version as 3 digit string ex. "535.86.05,"
            duration:               float     max rental duration in days
            external:               bool      show external offers in addition to datacenter offers
            flops_usd:              float     TFLOPs/$
            geolocation:            string    Two letter country code. Works with operators =, !=, in, notin (e.g. geolocation not in ['XV','XZ'])
            gpu_arch                string    host machine gpu architecture (e.g. nvidia, amd)
            gpu_max_power           float     GPU power limit (watts)
            gpu_max_temp            float     GPU temp limit (C)
            gpu_mem_bw:             float     GPU memory bandwidth in GB/s
            gpu_name:               string    GPU model name (no quotes, replace spaces with underscores, ie: RTX_3090 rather than 'RTX 3090')
            gpu_ram:                float     per GPU RAM in GB
            gpu_total_ram:          float     total GPU RAM in GB
            gpu_frac:               float     Ratio of GPUs in the offer to gpus in the system
            gpu_display_active:     bool      True if the GPU has a display attached
            has_avx:                bool      CPU supports AVX instruction set.
            id:                     int       instance unique ID
            inet_down:              float     internet download speed in Mb/s
            inet_down_cost:         float     internet download bandwidth cost in $/GB
            inet_up:                float     internet upload speed in Mb/s
            inet_up_cost:           float     internet upload bandwidth cost in $/GB
            machine_id              int       machine id of instance
            min_bid:                float     current minimum bid price in $/hr for interruptible
            num_gpus:               int       # of GPUs
            pci_gen:                float     PCIE generation
            pcie_bw:                float     PCIE bandwidth (CPU to GPU)
            reliability:            float     machine reliability score (see FAQ for explanation)
            rentable:               bool      is the instance currently rentable
            rented:                 bool      allow/disallow duplicates and potential conflicts with existing stopped instances
            storage_cost:           float     storage cost in $/GB/month
            static_ip:              bool      is the IP addr static/stable
            total_flops:            float     total TFLOPs from all GPUs
            ubuntu_version          string    host machine ubuntu OS version
            verified:               bool      is the machine verified
            vms_enabled:            bool      is the machine a VM instance
    """),
    aliases=hidden_aliases(["search instances"]),
)
def search__offers(args):
    """Creates a query based on search parameters as in the examples above.

    :param argparse.Namespace args: should supply all the command-line options
    """

    try:

        if args.no_default:
            query = {}
        else:
            query = {"verified": {"eq": True}, "external": {"eq": False}, "rentable": {"eq": True}, "rented": {"eq": False}}
            #query = {"verified": {"eq": True}, "external": {"eq": False}, "rentable": {"eq": True} }

        if args.query is not None:
            query = parse_query(args.query, query, offers_fields, offers_alias, offers_mult)

        order = []
        for name in args.order.split(","):
            name = name.strip()
            if not name: continue
            direction = "asc"
            field = name
            if name.strip("-") != name:
                direction = "desc"
                field = name.strip("-")
            if name.strip("+") != name:
                direction = "asc"
                field = name.strip("+")
            #print(f"{field} {name} {direction}")
            if field in offers_alias:
                field = offers_alias[field];
            order.append([field, direction])

        query["order"] = order
        query["type"] = args.type
        if (args.limit):
            query["limit"] = int(args.limit)
        query["allocated_storage"] = args.storage
        # For backwards compatibility, support --type=interruptible option
        if query["type"] == 'interruptible':
            query["type"] = 'bid'
        if args.disable_bundling:
            query["disable_bundling"] = True
    except ValueError as e:
        print("Error: ", e)
        return 1

    new_search_ept = args.new
    
    #json_blob = {"select_cols" : ['*'], "q" : query}
    json_blob = query

    if new_search_ept:
        #geolocation = query.pop("geolocation", None)
        #query = {'reliability2': {'gt': '0.1'}}
        json_blob = {"select_cols" : ['*'], "q" : query}
        url = apiurl(args, "/search/asks/")
        stime = time.time()

        if (args.explain):
            print("request json: ")
            print(json_blob)

        r = http_put(args, url, headers=headers, json=json_blob)
        etime = time.time()
        print(f"request took {etime-stime}s")

    else:
        if (args.explain):
            print("request json: ")
            print(json_blob)
        #url = apiurl(args, "/bundles", {"q": query})
        #r = requests.get(url, headers=headers)
        url = apiurl(args, "/bundles/")
        r = http_post(args, url, headers=headers, json=json_blob)

    r.raise_for_status()
   
    if (r.headers.get('Content-Type') != 'application/json'):
        print(f"invalid return Content-Type: {r.headers.get('Content-Type')}")
        return   

    rows = r.json()["offers"]

    # TODO: add this post-query geolocation filter to the database call rather than handling it locally
    if 'rented' in query:
        filter_q  = query['rented']
        filter_op = list(filter_q.keys())[0]
        target    = filter_q[filter_op]
        new_rows  = []
        for row in rows:
            rented = False
            if "rented" in row and row["rented"] is not None:
                rented = row["rented"]
            if filter_op == "eq" and rented == target:
                new_rows.append(row)
            if filter_op == "neq" and rented != target:
                new_rows.append(row)
            if filter_op == "in" and rented in target:
                new_rows.append(row)
            if filter_op == "notin" and rented not in target:
                new_rows.append(row)
        rows = new_rows

    if args.raw:
        return rows
    else:
        if args.type == "reserved":           
            display_table(rows, displayable_fields_reserved)
        else:
            display_table(rows, displayable_fields)


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

@parser.command(
    argument("query", help="Search query in simple query syntax (see below)", nargs="*", default=None),
    usage="vastai search templates [--help] [--api-key API_KEY] [--raw] <query>",
    help="Search for template results using custom query",
    epilog=deindent("""
        Query syntax:

            query = comparison comparison...
            comparison = field op value
            field = <name of a field>
            op = one of: <, <=, ==, !=, >=, >, in, notin
            value = <bool, int, float, string> | 'any' | [value0, value1, ...]
            bool: True, False

        note: to pass '>' and '<' on the command line, make sure to use quotes
        note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'

        Examples:

            # search for somewhat reliable single RTX 3090 instances, filter out any duplicates or offers that conflict with our existing stopped instances
            vastai search templates 'count_created > 100  creator_id in [38382,48982]'

        Available fields:

      Name                  Type       Description

    creator_id              int        ID of creator
    created_at              float      time of initial template creation (UTC epoch timestamp)
    count_created           int        #instances created (popularity)
    default_tag             string     image default tag
    docker_login_repo       string     image docker repository
    id                      int        template unique ID
    image                   string     image used for template
    jup_direct              bool       supports jupyter direct
    hash_id                 string     unique hash ID of template
    name                    string     displayable name
    recent_create_date      float      last time of instance creation (UTC epoch timestamp)
    recommended_disk_space  float      min disk space required
    recommended             bool       is templated on our recommended list
    ssh_direct              bool       supports ssh direct
    tag                     string     image tag
    use_ssh                 bool       supports ssh (direct or proxy)    """),
    aliases=hidden_aliases(["search templates"]),
)
def search__templates(args):
    """Creates a query based on search parameters as in the examples above.
    :param argparse.Namespace args: should supply all the command-line options
    """
    try:
        query = {}
        if args.query is not None:
            query = parse_query(args.query, query, templates_fields)
            query = fix_date_fields(query, ['created_at', 'recent_create_date'])

    except ValueError as e:
        print("Error: ", e)
        return 1  
    url = apiurl(args, "/template/", {"select_cols" : ['*'], "select_filters" : query})
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(r.text)
        r.raise_for_status()
    elif 'json' in r.headers.get("Content-Type"):
        rows = r.json().get('templates', [])
        if True: #args.raw:
            print(json.dumps(rows, indent=1, sort_keys=True))
        else:
            display_table(rows, displayable_fields)
    else:
        print(r.text)
        print("failed with error {r.status_code}".format(**locals()))

@parser.command(
    argument("-n", "--no-default", action="store_true", help="Disable default query"),
    argument("--limit", type=int, help=""),
    argument("--storage", type=float, default=1.0, help="Amount of storage to use for pricing, in GiB. default=1.0GiB"),
    argument("-o", "--order", type=str, help="Comma-separated list of fields to sort on. postfix field with - to sort desc. ex: -o 'disk_space,inet_up-'.  default='score-'", default='score-'),
    argument("query", help="Query to search for. default: 'external=false verified=true disk_space>=1', pass -n to ignore default", nargs="*", default=None),
    usage="vastai search volumes [--help] [--api-key API_KEY] [--raw] <query>",
    help="Search for volume offers using custom query",
    epilog=deindent("""
        Query syntax:

            query = comparison comparison...
            comparison = field op value
            field = <name of a field>
            op = one of: <, <=, ==, !=, >=, >, in, notin
            value = <bool, int, float, string> | 'any' | [value0, value1, ...]
            bool: True, False

        note: to pass '>' and '<' on the command line, make sure to use quotes
        note: to encode a string query value (ie for gpu_name), replace any spaces ' ' with underscore '_'

        Examples:

            # search for volumes with greater than 50GB of available storage and greater than 500 Mb/s upload and download speed
            vastai search volumes "disk_space>50 inet_up>500 inet_down>500"
            
        Available fields:

              Name                  Type       Description

            cpu_arch:               string    host machine cpu architecture (e.g. amd64, arm64)
            cuda_vers:              float     machine max supported cuda version (based on driver version)
            datacenter:             bool      show only datacenter offers
            disk_bw:                float     disk read bandwidth, in MB/s
            disk_space:             float     disk storage space, in GB
            driver_version:         string    machine's nvidia/amd driver version as 3 digit string ex. "535.86.05"
            duration:               float     max rental duration in days
            geolocation:            string    Two letter country code. Works with operators =, !=, in, notin (e.g. geolocation not in ['XV','XZ'])
            gpu_arch:               string    host machine gpu architecture (e.g. nvidia, amd)
            gpu_name:               string    GPU model name (no quotes, replace spaces with underscores, ie: RTX_3090 rather than 'RTX 3090')
            has_avx:                bool      CPU supports AVX instruction set.
            id:                     int       volume offer unique ID
            inet_down:              float     internet download speed in Mb/s
            inet_up:                float     internet upload speed in Mb/s
            machine_id:             int       machine id of volume offer
            pci_gen:                float     PCIE generation
            pcie_bw:                float     PCIE bandwidth (CPU to GPU)
            reliability:            float     machine reliability score (see FAQ for explanation)
            storage_cost:           float     storage cost in $/GB/month
            static_ip:              bool      is the IP addr static/stable
            total_flops:            float     total TFLOPs from all GPUs
            ubuntu_version:         string    host machine ubuntu OS version
            verified:               bool      is the machine verified
    """),
)
def search__volumes(args: argparse.Namespace):
    try:

        if args.no_default:
            query = {}
        else:
            query = {"verified": {"eq": True}, "external": {"eq": False}, "disk_space": {"gte": 1}}

        if args.query is not None:
            query = parse_query(args.query, query, vol_offers_fields, {}, offers_mult)

        order = []
        for name in args.order.split(","):
            name = name.strip()
            if not name: continue
            direction = "asc"
            field = name
            if name.strip("-") != name:
                direction = "desc"
                field = name.strip("-")
            if name.strip("+") != name:
                direction = "asc"
                field = name.strip("+")
            if field in offers_alias:
                field = offers_alias[field];
            order.append([field, direction])

        query["order"] = order
        if (args.limit):
            query["limit"] = int(args.limit)
        query["allocated_storage"] = args.storage
    except ValueError as e:
        print("Error: ", e)
        return 1

    json_blob = query

    if (args.explain):
        print("request json: ")
        print(json_blob)
    url = apiurl(args, "/volumes/search/")
    r = http_post(args, url, headers=headers, json=json_blob)

    r.raise_for_status()
   
    if (r.headers.get('Content-Type') != 'application/json'):
        print(f"invalid return Content-Type: {r.headers.get('Content-Type')}")
        return   

    rows = r.json()["offers"]
    
    if args.raw:
        return rows
    else:
        display_table(rows, vol_displayable_fields)




@parser.command(
    argument("new_api_key", help="Api key to set as currently logged in user"),
    usage="vastai set api-key APIKEY",
    help="Set api-key (get your api-key from the console/CLI)",
)
def set__api_key(args):
    """Caution: a bad API key will make it impossible to connect to the servers.
    :param argparse.Namespace args: should supply all the command-line options
    """
    with open(APIKEY_FILE, "w") as writer:
        writer.write(args.new_api_key)
    print("Your api key has been saved in {}".format(APIKEY_FILE))
    
    APIKEY_FILE_HOME = os.path.expanduser("~/.vast_api_key") # Legacy
    if os.path.exists(APIKEY_FILE_HOME):
        os.remove(APIKEY_FILE_HOME)
        print("Your api key has been removed from {}".format(APIKEY_FILE_HOME))



@parser.command(
    argument("--file", help="file path for params in json format", type=str),
    usage="vastai set user --file FILE",
    help="Update user data from json file",
    epilog=deindent("""

    Available fields:

    Name                            Type       Description

    ssh_key                         string
    paypal_email                    string
    wise_email                      string
    email                           string
    normalized_email                string
    username                        string
    fullname                        string
    billaddress_line1               string
    billaddress_line2               string
    billaddress_city                string
    billaddress_zip                 string
    billaddress_country             string
    billaddress_taxinfo             string
    balance_threshold_enabled       string
    balance_threshold               string
    autobill_threshold              string
    phone_number                    string
    tfa_enabled                     bool
    """),
)
def set__user(args):
    params = None
    with open(args.file, 'r') as file:
        params = json.load(file)
    url = apiurl(args, "/users/")
    r = requests.put(url, headers=headers, json=params)
    r.raise_for_status()
    print(f"{r.json()}")



@parser.command(
    argument("id", help="id of instance", type=int),
    usage="vastai ssh-url ID",
    help="ssh url helper",
)
def ssh_url(args):
    """

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    return _ssh_url(args, "ssh://")


@parser.command(
    argument("id",   help="id", type=int),
    usage="vastai scp-url ID",
    help="scp url helper",
)
def scp_url(args):
    """

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    return _ssh_url(args, "scp://")


def _ssh_url(args, protocol):

    json_object = None

    # Opening JSON file
    try:
        with open(f"{DIRS['temp']}/ssh_{args.id}.json", 'r') as openfile:
            json_object = json.load(openfile)
    except:
        pass

    port      = None
    ipaddr    = None

    if json_object is not None:
        ipaddr = json_object["ipaddr"]
        port   = json_object["port"]

    if ipaddr is None or ipaddr.endswith('.vast.ai'):
        req_url = apiurl(args, "/instances", {"owner": "me"});
        r = http_get(args, req_url);
        r.raise_for_status()
        rows = r.json()["instances"]
        if args.id:
            instance, = [r for r in rows if r['id'] == args.id]
        elif len(rows) > 1:
            print("Found multiple running instances")
            return 1
        else:
            instance, = rows

        ports     = instance.get("ports",{})
        port_22d  = ports.get("22/tcp",None)
        port      = -1
        try:
            if (port_22d is not None):
                ipaddr = instance["public_ipaddr"]
                port   = int(port_22d[0]["HostPort"])
            else:        
                ipaddr = instance["ssh_host"]
                port   = int(instance["ssh_port"])+1 if "jupyter" in instance["image_runtype"] else int(instance["ssh_port"])
        except:
            port = -1

    if (port > 0):
        print(f'{protocol}root@{ipaddr}:{port}')
    else:
        print(f'error: ssh port not found')

   
    # Writing to sample.json
    try:
        with open(f"{DIRS['temp']}/ssh_{args.id}.json", "w") as outfile:
            json.dump({"ipaddr":ipaddr, "port":port}, outfile)
    except:
        pass

@parser.command(
    argument("id", help="id of apikey to get", type=int),
    usage="vastai show api-key",
    help="Show an api-key",
)
def show__api_key(args):
    url = apiurl(args, "/auth/apikeys/{id}/".format(id=args.id))
    r = http_get(args, url, headers=headers)
    r.raise_for_status()
    print(r.json())

@parser.command(
    usage="vastai show api-keys",
    help="List your api-keys associated with your account",
)
def show__api_keys(args):
    url = apiurl(args, "/auth/apikeys/")
    r = http_get(args, url, headers=headers)
    r.raise_for_status()
    if args.raw:
        return r
    else:
        print(r.json())


@parser.command(
    usage="vastai show audit-logs [--api-key API_KEY] [--raw]",
    help="Display account's history of important actions"
)
def show__audit_logs(args):
    """
    Shows the history of ip address accesses to console.vast.ai endpoints

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    req_url = apiurl(args, "/audit_logs/")
    r = http_get(args, req_url)
    r.raise_for_status()
    rows = r.json()
    if args.raw:
        return rows
    else:
        display_table(rows, audit_log_fields)


@parser.command(
    usage="vastai show ssh-keys",
    help="List your ssh keys associated with your account",
)
def show__ssh_keys(args):
    url = apiurl(args, "/ssh/")
    r = http_get(args, url, headers=headers)
    r.raise_for_status()
    if args.raw:
        return r
    else:
        print(r.json())

@parser.command(
    usage="vastai show autogroups [--api-key API_KEY]",
    help="Display user's current autogroup groups",
    epilog=deindent("""
        Example: vastai show autogroups 
    """),
)
def show__autogroups(args):
    url = apiurl(args, "/autojobs/" )
    json_blob = {"client_id": "me", "api_key": args.api_key}
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_get(args, url, headers=headers,json=json_blob)
    r.raise_for_status()
    #print("autogroup list ".format(r.json()))

    if (r.status_code == 200):
        rj = r.json();
        if (rj["success"]):
            rows = rj["results"] 
            if args.raw:
                return rows
            else:
                #print(rows)
                print(json.dumps(rows, indent=1, sort_keys=True))
        else:
            print(rj["msg"]);

@parser.command(
    usage="vastai show endpoints [--api-key API_KEY]",
    help="Display user's current endpoint groups",
    epilog=deindent("""
        Example: vastai show endpoints
    """),
)
def show__endpoints(args):
    url = apiurl(args, "/endptjobs/" )
    json_blob = {"client_id": "me", "api_key": args.api_key}
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_get(args, url, headers=headers,json=json_blob)
    r.raise_for_status()
    #print("autogroup list ".format(r.json()))

    if (r.status_code == 200):
        rj = r.json();
        if (rj["success"]):
            rows = rj["results"] 
            if args.raw:
                return rows
            else:
                #print(rows)
                print(json.dumps(rows, indent=1, sort_keys=True))
        else:
            print(rj["msg"]);


@parser.command(
    usage="vastai show connections [--api-key API_KEY] [--raw]",
    help="Display user's cloud connections"
)
def show__connections(args):
    """
    Shows the stats on the machine the user is renting.

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    req_url = apiurl(args, "/users/cloud_integrations/");
    print(req_url)
    r = http_get(args, req_url, headers=headers);
    r.raise_for_status()
    rows = r.json()

    if args.raw:
        return rows
    else:
        display_table(rows, connection_fields)


@parser.command(
    argument("id", help="id of instance to get info for", type=int),
    usage="vastai show deposit ID [options]",
    help="Display reserve deposit info for an instance"
)
def show__deposit(args):
    """
    Shows reserve deposit info for an instance.

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    req_url = apiurl(args, "/instances/balance/{id}/".format(id=args.id) , {"owner": "me"} )
    r = http_get(args, req_url)
    r.raise_for_status()
    print(json.dumps(r.json(), indent=1, sort_keys=True))


@parser.command(
    argument("-q", "--quiet", action="store_true", help="only display numeric ids"),
    argument("-s", "--start_date", help="start date and time for report. Many formats accepted", type=str),
    argument("-e", "--end_date", help="end date and time for report. Many formats accepted ", type=str),
    argument("-m", "--machine_id", help="Machine id (optional)", type=int),
    usage="vastai show earnings [OPTIONS]",
    help="Get machine earning history reports",
)
def show__earnings(args):
    """
    Show earnings history for a time range, optionally per machine. Various options available to limit time range and type of items.

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """

    Minutes = 60.0;
    Hours	= 60.0*Minutes;
    Days	= 24.0*Hours;
    Years	= 365.0*Days;
    cday    = time.time() / Days
    sday = cday - 1.0
    eday = cday - 1.0

    try:
        import dateutil
        from dateutil import parser

    except ImportError:
        print("""\nWARNING: Missing dateutil, can't parse time format""")

    if args.end_date:
        try:
            end_date = dateutil.parser.parse(str(args.end_date))
            end_date_txt = end_date.isoformat()
            end_timestamp = time.mktime(end_date.timetuple())
            eday = end_timestamp / Days
        except ValueError as e:
            print(f"Warning: Invalid end date format! Ignoring end date! \n {str(e)}")

    if args.start_date:
        try:
            start_date = dateutil.parser.parse(str(args.start_date))
            start_date_txt = start_date.isoformat()
            start_timestamp = time.mktime(start_date.timetuple())
            sday = start_timestamp / Days
        except ValueError:
            print(f"Warning: Invalid start date format! Ignoring start date! \n {str(e)}")



    req_url = apiurl(args, "/users/me/machine-earnings", {"owner": "me", "sday": sday, "eday": eday, "machid" :args.machine_id});
    r = http_get(args, req_url)
    r.raise_for_status()
    rows = r.json()

    print(json.dumps(rows, indent=1, sort_keys=True))


def sum(X, k):
    y = 0
    for x in X:
        a = float(x.get(k,0))
        y += a
    return y

def select(X,k):
    Y = set()
    for x in X:
        v = x.get(k,None)
        if v is not None:
            Y.add(v)
    return Y

@parser.command(
    argument("-s", "--show-values", action="store_true", help="Show the values of environment variables"),
    usage="vastai show env-vars [-s]",
    help="Show user environment variables",
)
def show__env_vars(args):
    """Show the environment variables for the current user."""
    url = apiurl(args, "/secrets/")
    r = http_get(args, url, headers=headers)
    r.raise_for_status()

    env_vars = r.json().get("secrets", {})

    if args.raw:
        if not args.show_values:
            # Replace values with placeholder in raw output
            masked_env_vars = {k: "*****" for k, v in env_vars.items()}
            # indent was 2
            return masked_env_vars
        else:
            return env_vars
    else:
        if not env_vars:
            print("No environment variables found.")
        else:
            for key, value in env_vars.items():
                print(f"Name: {key}")
                if args.show_values:
                    print(f"Value: {value}")
                else:
                    print("Value: *****")
                print("---")

    if not args.show_values:
        print("\nNote: Values are hidden. Use --show-values or -s option to display them.")

@parser.command(
    argument("-q", "--quiet", action="store_true", help="only display numeric ids"),
    argument("-s", "--start_date", help="start date and time for report. Many formats accepted (optional)", type=str),
    argument("-e", "--end_date", help="end date and time for report. Many formats accepted (optional)", type=str),
    argument("-c", "--only_charges", action="store_true", help="Show only charge items"),
    argument("-p", "--only_credits", action="store_true", help="Show only credit items"),
    argument("--instance_label", help="Filter charges on a particular instance label (useful for autoscaler groups)"),
    usage="vastai show invoices [OPTIONS]",
    help="Get billing history reports",
)
def show__invoices(args):
    """
    Show current payments and charges. Various options available to limit time range and type
    of items. Default is to show everything for user's entire billing history.

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """

    sdate,edate = convert_dates_to_timestamps(args)
    req_url = apiurl(args, "/users/me/invoices", {"owner": "me", "sdate":sdate, "edate":edate, "inc_charges" : not args.only_credits});

    r = http_get(args, req_url)
    r.raise_for_status()
    rows = r.json()["invoices"]
    # print("Timestamp for first row: ", rows[0]["timestamp"])
    invoice_filter_data = filter_invoice_items(args, rows)
    rows = invoice_filter_data["rows"]
    filter_header = invoice_filter_data["header_text"]

    contract_ids = None

    if (args.instance_label):
        #print(rows)
        contract_ids = select(rows, 'instance_id')
        #print(contract_ids)

        url = apiurl(args, f"/contracts/fetch/")

        req_json = {
            "label": args.instance_label,
            "contract_ids": list(contract_ids)
        }

        if (args.explain):
            print("request json: ")
            print(req_json)
        
        result = http_post(args, url, headers=headers,json=req_json)
        result.raise_for_status()
        filtered_rows = result.json()["contracts"]
        #print(rows)

        contract_ids = select(filtered_rows, 'id')
        #print(contract_ids)

        rows2 = []
        for row in rows:
            id = row.get("instance_id", None)
            if id in contract_ids:
                rows2.append(row)
        rows = rows2

    current_charges = r.json()["current"]
    if args.quiet:
        for row in rows:
            id = row.get("id", None)
            if id is not None:
                print(id)
    elif args.raw:
        # sort keys
        return rows
        # print("Current: ", current_charges)
    else:
        print(filter_header)
        display_table(rows, invoice_fields)
        print(f"Total: ${sum(rows, 'amount')}")
        print("Current: ", current_charges)


@parser.command(
    argument("id", help="id of instance to get", type=int),
    usage="vastai show instance [--api-key API_KEY] [--raw]",
    help="Display user's current instances"
)
def show__instance(args):
    """
    Shows the stats on the machine the user is renting.

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """

    #req_url = apiurl(args, "/instance", {"owner": "me"});
    req_url = apiurl(args, "/instances/{id}/".format(id=args.id) , {"owner": "me"} )
   
    #r = http_get(req_url)
    r = http_get(args, req_url)
    r.raise_for_status()
    row = r.json()["instances"]
    row['duration'] = time.time() - row['start_date']
    row['extra_env'] = {env_var[0]: env_var[1] for env_var in row['extra_env']}
    if args.raw:
        return row
    else:
        #print(row)
        display_table([row], instance_fields)

@parser.command(
    argument("-q", "--quiet", action="store_true", help="only display numeric ids"),
    usage="vastai show instances [OPTIONS] [--api-key API_KEY] [--raw]",
    help="Display user's current instances"
)
def show__instances(args = {}, extra = {}):
    """
    Shows the stats on the machine the user is renting.

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    req_url = apiurl(args, "/instances", {"owner": "me"});
    #r = http_get(req_url)
    r = http_get(args, req_url)
    r.raise_for_status()
    rows = r.json()["instances"]
    for row in rows:
        row = {k: strip_strings(v) for k, v in row.items()} 
        row['duration'] = time.time() - row['start_date']
        row['extra_env'] = {env_var[0]: env_var[1] for env_var in row['extra_env']}
    if 'internal' in extra:
        return [str(row[extra['field']]) for row in rows]
    elif args.quiet:
        for row in rows:
            id = row.get("id", None)
            if id is not None:
                print(id)
    elif args.raw:
        return rows
    else:
        display_table(rows, instance_fields)




@parser.command(
    usage="vastai show ipaddrs [--api-key API_KEY] [--raw]",
    help="Display user's history of ip addresses"
)
def show__ipaddrs(args):
    """
    Shows the history of ip address accesses to console.vast.ai endpoints

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """

    req_url = apiurl(args, "/users/me/ipaddrs", {"owner": "me"});
    r = http_get(args, req_url);
    r.raise_for_status()
    rows = r.json()["results"]
    if args.raw:
        return rows
    else:
        display_table(rows, ipaddr_fields)



@parser.command(
    argument("-q", "--quiet", action="store_true", help="display information about user"),
    usage="vastai show user [OPTIONS]",
    help="Get current user data",
    epilog=deindent("""
        Shows stats for logged-in user. These include user balance, email, and ssh key. Does not show API key.
    """)
)
def show__user(args):
    """
    Shows stats for logged-in user. Does not show API key.

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    req_url = apiurl(args, "/users/current", {"owner": "me"});
    r = http_get(args, req_url);
    r.raise_for_status()
    user_blob = r.json()
    user_blob.pop("api_key")

    if args.raw:
        return user_blob
    else:
        display_table([user_blob], user_fields)

@parser.command(
    argument("-q", "--quiet", action="store_true", help="display subaccounts from current user"),
    usage="vastai show subaccounts [OPTIONS]",
    help="Get current subaccounts"
)
def show__subaccounts(args):
    """
    Shows stats for logged-in user. Does not show API key.

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    req_url = apiurl(args, "/subaccounts", {"owner": "me"});
    r = http_get(args, req_url);
    r.raise_for_status()
    rows = r.json()["users"]
    if args.raw:
        return rows
    else:
        display_table(rows, user_fields)

@parser.command(
    usage="vastai show members",
    help="Show your team members",
)
def show__members(args):
    url = apiurl(args, "/team/members/")
    r = http_get(args, url, headers=headers)
    r.raise_for_status()

    if args.raw:
        return r
    else:
        print(r.json())

@parser.command(
    argument("NAME", help="name of the role", type=str),
    usage="vastai show team-role NAME",
    help="Show your team role",
)
def show__team_role(args):
    url = apiurl(args, "/team/roles/{id}/".format(id=args.NAME))
    r = http_get(args, url, headers=headers)
    r.raise_for_status()
    print(json.dumps(r.json(), indent=1, sort_keys=True))

@parser.command(
    usage="vastai show team-roles",
    help="Show roles for a team"
)
def show__team_roles(args):
    url = apiurl(args, "/team/roles-full/")
    r = http_get(args, url, headers=headers)
    r.raise_for_status()

    if args.raw:
        return r
    else:
        print(r.json())


@parser.command(
    usage="vastai show volumes",
    help="Show stats on owned volumes.",
    epilog=deindent("""
        Show stats on owned volumes
    """)
)
def show__volumes(args: argparse.Namespace):
    req_url = apiurl(args, "/volumes", {"owner": "me"});
    r = http_get(args, req_url)
    r.raise_for_status()
    rows = r.json()["volumes"]
    processed = []
    for row in rows:
        row = {k: strip_strings(v) for k, v in row.items()} 
        row['duration'] = time.time() - row['start_date']
        processed.append(row)
    if args.raw:
        return processed
    else:
        display_table(processed, volume_fields, replace_spaces=False)


@parser.command(
    argument("recipient", help="email (or id) of recipient account", type=str),
    argument("amount",    help="$dollars of credit to transfer ", type=float),
    argument("--skip",    help="skip confirmation", action="store_true", default=False),
    usage="vastai transfer credit RECIPIENT AMOUNT",
    help="Transfer credits to another account",
    epilog=deindent("""
        Transfer (amount) credits to account with email (recipient).
    """),
)
def transfer__credit(args: argparse.Namespace):
    url = apiurl(args, "/commands/transfer_credit/")
 
    if not args.skip:
        print(f"Transfer ${args.amount} credit to account {args.recipient}?  This is irreversible.")
        ok = input("Continue? [y/n] ")
        if ok.strip().lower() != "y":
            return

    json_blob = {
        "sender":    "me",
        "recipient": args.recipient,
        "amount":    args.amount,
    }
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, url,  headers=headers,json=json_blob)
    r.raise_for_status()

    if (r.status_code == 200):
        rj = r.json();
        if (rj["success"]):
            print(f"Sent {args.amount} to {args.recipient} ".format(r.json()))
        else:
            print(rj["msg"]);
    else:
        print(r.text);
        print("failed with error {r.status_code}".format(**locals()));

@parser.command(
    argument("id", help="id of autoscale group to update", type=int),
    argument("--min_load", help="minimum floor load in perf units/s  (token/s for LLms)", type=float),
    argument("--target_util",      help="target capacity utilization (fraction, max 1.0, default 0.9)", type=float),
    argument("--cold_mult",   help="cold/stopped instance capacity target as multiple of hot capacity target (default 2.5)", type=float),
    argument("--test_workers",help="number of workers to create to get an performance estimate for while initializing autogroup (default 3)", type=int),
    argument("--gpu_ram",   help="estimated GPU RAM req  (independent of search string)", type=float),
    argument("--template_hash",   help="template hash (**Note**: if you use this field, you can skip search_params, as they are automatically inferred from the template)", type=str),
    argument("--template_id",   help="template id", type=int),
    argument("--search_params",   help="search param string for search offers    ex: \"gpu_ram>=23 num_gpus=2 gpu_name=RTX_4090 inet_down>200 direct_port_count>2 disk_space>=64\"", type=str),
    argument("-n", "--no-default", action="store_true", help="Disable default search param query args"),
    argument("--launch_args",   help="launch args  string for create instance  ex: \"--onstart onstart_wget.sh  --env '-e ONSTART_PATH=https://s3.amazonaws.com/vast.ai/onstart_OOBA.sh' --image atinoda/text-generation-webui:default-nightly --disk 64\"", type=str),
    argument("--endpoint_name",   help="deployment endpoint name (allows multiple autoscale groups to share same deployment endpoint)", type=str),
    argument("--endpoint_id",   help="deployment endpoint id (allows multiple autoscale groups to share same deployment endpoint)", type=int),
    usage="vastai update autogroup ID [OPTIONS]",
    help="Update an existing autoscale group",
    epilog=deindent("""
        Example: vastai update autogroup 4242 --min_load 100 --target_util 0.9 --cold_mult 2.0 --search_params \"gpu_ram>=23 num_gpus=2 gpu_name=RTX_4090 inet_down>200 direct_port_count>2 disk_space>=64\" --launch_args \"--onstart onstart_wget.sh  --env '-e ONSTART_PATH=https://s3.amazonaws.com/vast.ai/onstart_OOBA.sh' --image atinoda/text-generation-webui:default-nightly --disk 64\" --gpu_ram 32.0 --endpoint_name "LLama" --endpoint_id 2
    """),
)
def update__autogroup(args):
    id  = args.id
    url = apiurl(args, f"/autojobs/{id}/" )
    if args.no_default:
        query = ""
    else:
        query = " verified=True rentable=True rented=False"
    json_blob = {"client_id": "me", "autojob_id": args.id, "min_load": args.min_load, "target_util": args.target_util, "cold_mult": args.cold_mult, "test_workers" : args.test_workers, "template_hash": args.template_hash, "template_id": args.template_id, "search_params": args.search_params + query, "launch_args": args.launch_args, "gpu_ram": args.gpu_ram, "endpoint_name": args.endpoint_name, "endpoint_id": args.endpoint_id}
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, url,  headers=headers,json=json_blob)
    r.raise_for_status()
    if 'application/json' in r.headers.get('Content-Type', ''):
        try:
            print("autogroup update {}".format(r.json()))
        except requests.exceptions.JSONDecodeError:
            print("The response is not valid JSON.")
            print(r)
            print(r.text)  # Print the raw response to help with debugging.
    else:
        print("The response is not JSON. Content-Type:", r.headers.get('Content-Type'))
        print(r.text)

@parser.command(
    argument("id", help="id of endpoint group to update", type=int),
    argument("--min_load", help="minimum floor load in perf units/s  (token/s for LLms)", type=float),
    argument("--target_util",      help="target capacity utilization (fraction, max 1.0, default 0.9)", type=float),
    argument("--cold_mult",   help="cold/stopped instance capacity target as multiple of hot capacity target (default 2.5)", type=float),
    argument("--cold_workers", help="min number of workers to keep 'cold' when you have no load (default 5)", type=int),
    argument("--max_workers", help="max number of workers your endpoint group can have (default 20)", type=int),
    argument("--endpoint_name",   help="deployment endpoint name (allows multiple autoscale groups to share same deployment endpoint)", type=str),
    usage="vastai update endpoint ID [OPTIONS]",
    help="Update an existing endpoint group",
    epilog=deindent("""
        Example: vastai update endpoint 4242 --min_load 100 --target_util 0.9 --cold_mult 2.0 --endpoint_name "LLama"
    """),
)
def update__endpoint(args):
    id  = args.id
    url = apiurl(args, f"/endptjobs/{id}/" )
    json_blob = {"client_id": "me", "endptjob_id": args.id, "min_load": args.min_load, "target_util": args.target_util, "cold_mult": args.cold_mult, "cold_workers": args.cold_workers, "max_workers" : args.max_workers, "endpoint_name": args.endpoint_name}
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, url,  headers=headers,json=json_blob)
    r.raise_for_status()
    if 'application/json' in r.headers.get('Content-Type', ''):
        try:
            print("update endpoint {}".format(r.json()))
        except requests.exceptions.JSONDecodeError:
            print("The response is not valid JSON.")
            print(r)
            print(r.text)  # Print the raw response to help with debugging.
    else:
        print("The response is not JSON. Content-Type:", r.headers.get('Content-Type'))
        print(r.text)

@parser.command(
    argument("name", help="Environment variable name to update", type=str),
    argument("value", help="New environment variable value", type=str),
    usage="vastai update env-var <name> <value>",
    help="Update an existing user environment variable",
)
def update__env_var(args):
    """Update an existing environment variable for the current user."""
    url = apiurl(args, "/secrets/")
    data = {"key": args.name, "value": args.value}
    r = http_put(args, url, headers=headers, json=data)
    r.raise_for_status()

    result = r.json()
    if result.get("success"):
        print(result.get("msg", "Environment variable updated successfully."))
    else:
        print(f"Failed to update environment variable: {result.get('msg', 'Unknown error')}")

@parser.command(
    argument("id", help="id of instance to update", type=int),
    argument("--template_id", help="new template ID to associate with the instance", type=int),
    argument("--template_hash_id", help="new template hash ID to associate with the instance", type=str),
    argument("--image", help="new image UUID for the instance", type=str),
    argument("--args", help="new arguments for the instance", type=str),
    argument("--env", help="new environment variables for the instance", type=json.loads),
    argument("--onstart", help="new onstart script for the instance", type=str),
    usage="vastai update instance ID [OPTIONS]",
    help="Update recreate an instance from a new/updated template",
    epilog=deindent("""
        Example: vastai update instance 1234 --template_hash_id 661d064bbda1f2a133816b6d55da07c3
    """),
)
def update__instance(args):
    """
    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    url = apiurl(args, f"/instances/update_template/{args.id}/")
    json_blob = {"id": args.id}
    
    if args.template_id:
        json_blob["template_id"] = args.template_id
    if args.template_hash_id:
        json_blob["template_hash_id"] = args.template_hash_id
    if args.image:
        json_blob["image"] = args.image
    if args.args:
        json_blob["args"] = args.args
    if args.env:
        json_blob["env"] = args.env
    if args.onstart:
        json_blob["onstart"] = args.onstart

    if args.explain:
        print("request json: ")
        print(json_blob)
    
    r = http_put(args, url, headers=headers, json=json_blob)

    if r.status_code == 200:
        response_data = r.json()
        if response_data.get("success"):
            print(f"Instance {args.id} updated successfully.")
            print("Updated instance details:")
            print(response_data.get("updated_instance"))
        else:
            print(f"Failed to update instance {args.id}: {response_data.get('msg')}")
    else:
        print(f"Failed to update instance {args.id} with error {r.status_code}: {r.text}")


@parser.command(
    argument("id", help="id of the role", type=int),
    argument("--name", help="name of the template", type=str),
    argument("--permissions", help="file path for json encoded permissions, look in the docs for more information", type=str),
    usage="vastai update team-role ID --name NAME --permissions PERMISSIONS",
    help="Update an existing team role",
)
def update__team_role(args):
    url = apiurl(args, "/team/roles/{id}/".format(id=args.id))
    permissions = load_permissions_from_file(args.permissions)
    r = http_put(args, url,  headers=headers, json={"name": args.name, "permissions": permissions})
    r.raise_for_status()
    if args.raw:
        return r
    else:
        print(json.dumps(r.json(), indent=1))



@parser.command(
    argument("HASH_ID", help="hash id of the template", type=str),
    *get_template_arguments(),
    usage="vastai update template HASH_ID",
    help="Update an existing template",
    epilog=deindent("""
        Update a template

        Example: 
            vastai update template c81e7ab0e928a508510d1979346de10d --name "tgi-llama2-7B-quantized" --image "ghcr.io/huggingface/text-generation-inference:1.0.3" 
                                    --env "-p 3000:3000 -e MODEL_ARGS='--model-id TheBloke/Llama-2-7B-chat-GPTQ --quantize gptq'" 
                                    --onstart-cmd 'wget -O - https://raw.githubusercontent.com/vast-ai/vast-pyworker/main/scripts/launch_tgi.sh | bash' 
                                    --search_params "gpu_ram>=23 num_gpus=1 gpu_name=RTX_3090 inet_down>128 direct_port_count>3 disk_space>=192 driver_version>=535086005 rented=False" 
                                    --disk 8.0 --ssh --direct
    """)
)
def update__template(args):
    url = apiurl(args, f"/template/")
    jup_direct = args.jupyter and args.direct
    ssh_direct = args.ssh and args.direct
    use_ssh = args.ssh or args.jupyter
    runtype = "jupyter" if args.jupyter else ("ssh" if args.ssh else "args")
    if args.login:
        login = args.login.split(" ")
        docker_login_repo = login[0]
    else:
        docker_login_repo = None
    default_search_query = {}
    if not args.no_default:
        default_search_query = {"verified": {"eq": True}, "external": {"eq": False}, "rentable": {"eq": True}, "rented": {"eq": False}}
    
    extra_filters = parse_query(args.search_params, default_search_query, offers_fields, offers_alias, offers_mult)
    template = {
        "hash_id": args.HASH_ID,
        "name" : args.name,
        "image" : args.image,
        "tag" : args.image_tag,
        "href" : args.href,
        "repo" : args.repo,
        "env" : args.env, #str format
        "onstart" : args.onstart_cmd, #don't accept file name for now
        "jup_direct" : jup_direct,
        "ssh_direct" : ssh_direct,
        "use_jupyter_lab" : args.jupyter_lab,
        "runtype" : runtype,
        "use_ssh" : use_ssh,
        "jupyter_dir" : args.jupyter_dir,
        "docker_login_repo" : docker_login_repo, #can't store username/password with template for now
        "extra_filters" : extra_filters,
        "recommended_disk_space" : args.disk_space,
        "readme": args.readme,
        "readme_visible": not args.hide_readme,
        "desc": args.desc,
        "private": not args.public,
    }

    json_blob = template
    if (args.explain):
        print("request json: ")
        print(json_blob)

    r = http_put(args, url, headers=headers, json=json_blob)
    r.raise_for_status()
    try:
        rj = r.json()
        if rj["success"]:
            print(f"updated template: {json.dumps(rj['template'], indent=1)}")
        else:
            print("template update failed")
    except requests.exceptions.JSONDecodeError as e:
        print(str(e))
        #print(r.text)
        print(r.status_code)



@parser.command(
    argument("id", help="id of the ssh key to update", type=int),
    argument("ssh_key", help="value of the ssh_key", type=str),
    usage="vastai update ssh-key id ssh_key",
    help="Update an existing ssh key",
)
def update__ssh_key(args):
    ssh_key = get_ssh_key(args.ssh_key)
    url = apiurl(args, "/ssh/{id}/".format(id=args.id))
    r = http_put(args, url,  headers=headers, json={"ssh_key": ssh_key})
    r.raise_for_status()
    print(r.json())

def convert_dates_to_timestamps(args):
    selector_flag = ""
    end_timestamp = time.time()
    start_timestamp = time.time() - (24*60*60)
    start_date_txt = ""
    end_date_txt = ""

    import dateutil
    from dateutil import parser

    if args.end_date:
        try:
            end_date = dateutil.parser.parse(str(args.end_date))
            end_date_txt = end_date.isoformat()
            end_timestamp = time.mktime(end_date.timetuple())
        except ValueError as e:
            print(f"Warning: Invalid end date format! Ignoring end date! \n {str(e)}")
    
    if args.start_date:
        try:
            start_date = dateutil.parser.parse(str(args.start_date))
            start_date_txt = start_date.isoformat()
            start_timestamp = time.mktime(start_date.timetuple())
        except ValueError as e:
            print(f"Warning: Invalid start date format! Ignoring end date! \n {str(e)}")

    return start_timestamp, end_timestamp


def filter_invoice_items(args: argparse.Namespace, rows: List) -> Dict:
    """This applies various filters to the invoice items. Currently it filters on start and end date and applies the
    'only_charge' and 'only_credits' options.invoice_number

    :param argparse.Namespace args: should supply all the command-line options
    :param List rows: The rows of items in the invoice

    :rtype List: Returns the filtered list of rows.

    """

    try:
        #import vast_pdf
        import dateutil
        from dateutil import parser

    except ImportError:
        print("""\nWARNING: The 'vast_pdf' library is not present. This library is used to print invoices in PDF format. If
        you do not need this feature you can ignore this message. To get the library you should download the vast-python
        github repository. Just do 'git@github.com:vast-ai/vast-python.git' and then 'cd vast-python'. Once in that
        directory you can run 'vast.py' and it will have access to 'vast_pdf.py'. The library depends on a Python
        package called Borb to make the PDF files. To install this package do 'pip3 install borb'.\n""")

    """
    try:
        vast_pdf
    except NameError:
        vast_pdf = Object()
        vast_pdf.invoice_number = -1
    """

    selector_flag = ""
    end_timestamp: float = 9999999999
    start_timestamp: float = 0
    start_date_txt = ""
    end_date_txt = ""

    if args.end_date:
        try:
            end_date = dateutil.parser.parse(str(args.end_date))
            end_date_txt = end_date.isoformat()
            end_timestamp = time.mktime(end_date.timetuple())
        except ValueError:
            print("Warning: Invalid end date format! Ignoring end date!")
    if args.start_date:
        try:
            start_date = dateutil.parser.parse(str(args.start_date))
            start_date_txt = start_date.isoformat()
            start_timestamp = time.mktime(start_date.timetuple())
        except ValueError:
            print("Warning: Invalid start date format! Ignoring start date!")

    if args.only_charges:
        type_txt = "Only showing charges."
        selector_flag = "only_charges"

        def type_filter_fn(row):
            return True if row["type"] == "charge" else False
    elif args.only_credits:
        type_txt = "Only showing credits."
        selector_flag = "only_credits"

        def type_filter_fn(row):
            return True if row["type"] == "payment" else False
    else:
        type_txt = ""

        def type_filter_fn(row):
            return True

    if args.end_date:
        if args.start_date:
            header_text = f'Invoice items after {start_date_txt} and before {end_date_txt}.'
        else:
            header_text = f'Invoice items before {end_date_txt}.'
    elif args.start_date:
        header_text = f'Invoice items after {start_date_txt}.'
    else:
        header_text = " "

    header_text = header_text + " " + type_txt

    rows = list(filter(lambda row: end_timestamp >= (row["timestamp"] or 0.0) >= start_timestamp and type_filter_fn(row) and float(row["amount"]) != 0, rows))

    if start_date_txt:
        start_date_txt = "S:" + start_date_txt

    if end_date_txt:
        end_date_txt = "E:" + end_date_txt

    now = date.today()
    invoice_number: int = now.year * 12 + now.month - 1


    pdf_filename_fields = list(filter(lambda fld: False if fld == "" else True,
                                      [str(invoice_number),
                                       start_date_txt,
                                       end_date_txt,
                                       selector_flag]))

    filename = "invoice_" + "-".join(pdf_filename_fields) + ".pdf"
    return {"rows": rows, "header_text": header_text, "pdf_filename": filename}





#@parser.command(
#    argument("-q", "--quiet", action="store_true", help="only display numeric ids"),
#    argument("-s", "--start_date", help="start date and time for report. Many formats accepted (optional)", type=str),
#    argument("-e", "--end_date", help="end date and time for report. Many formats accepted (optional)", type=str),
#    argument("-c", "--only_charges", action="store_true", help="Show only charge items."),
#    argument("-p", "--only_credits", action="store_true", help="Show only credit items."),
#    usage="vastai generate pdf-invoices [OPTIONS]",
#)
#def generate__pdf_invoices(args):
#    """
#    Makes a PDF version of the data returned by the "show invoices" command. Takes the same command line args as that
#    command.
#
#    :param argparse.Namespace args: should supply all the command-line options
#    :rtype:
#    """
#
#    try:
#        import vast_pdf
#    except ImportError:
#        print("""\nWARNING: The 'vast_pdf' library is not present. This library is used to print invoices in PDF format. If
#        you do not need this feature you can ignore this message. To get the library you should download the vast-python
#        github repository. Just do 'git@github.com:vast-ai/vast-python.git' and then 'cd vast-python'. Once in that
#        directory you can run 'vast.py' and it will have access to 'vast_pdf.py'. The library depends on a Python
#        package called Borb to make the PDF files. To install this package do 'pip3 install borb'.\n""")
#
#    sdate,edate = convert_dates_to_timestamps(args)
#    req_url_inv = apiurl(args, "/users/me/invoices", {"owner": "me", "sdate":sdate, "edate":edate})
#
#    r_inv = http_get(args, req_url_inv, headers=headers)
#    r_inv.raise_for_status()
#    rows_inv = r_inv.json()["invoices"]
#    invoice_filter_data = filter_invoice_items(args, rows_inv)
#    rows_inv = invoice_filter_data["rows"]
#    req_url = apiurl(args, "/users/current", {"owner": "me"})
#    r = http_get(args, req_url)
#    r.raise_for_status()
#    user_blob = r.json()
#    user_blob = translate_null_strings_to_blanks(user_blob)
#
#    if args.raw:
#        print(json.dumps(rows_inv, indent=1, sort_keys=True))
#        print("Current: ", user_blob)
#        print("Raw mode")
#    else:
#        display_table(rows_inv, invoice_fields)
#        vast_pdf.generate_invoice(user_blob, rows_inv, invoice_filter_data)
#
#


@parser.command(
    argument("id", help="id of machine to cancel maintenance(s) for", type=int),
    usage="vastai cancel maint id",
    help="[Host] Cancel maint window",
    epilog=deindent("""
        For deleting a machine's scheduled maintenance window(s), use this cancel maint command.    
        Example: vastai cancel maint 8207
    """),
    )
def cancel__maint(args):
    """
    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    url = apiurl(args, "/machines/{id}/cancel_maint/".format(id=args.id))

    print(f"Cancelling scheduled maintenance window(s) for machine {args.id}.")
    ok = input("Continue? [y/n] ")
    if ok.strip().lower() != "y":
        return

    json_blob = {"client_id": "me", "machine_id": args.id}
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, url,  headers=headers,json=json_blob)
    r.raise_for_status()
    print(r.text)
    print(f"Cancel maintenance window(s) scheduled for machine {args.id} success".format(r.json()))


def cleanup_machine(args, machine_id):
    req_url = apiurl(args, f"/machines/{machine_id}/cleanup/")

    if (args.explain):
        print("request json: ")
    r = http_put(args, req_url, headers=headers, json={})

    if (r.status_code == 200):
        rj = r.json()
        if (rj["success"]):
            print(json.dumps(r.json(), indent=1))
        else:
            if args.raw:
                return r
            else:
                print(rj["msg"])
    else:
        print(r.text)
        print("failed with error {r.status_code}".format(**locals()))

@parser.command(
    argument("id", help="id of machine to cleanup", type=int),
    usage="vastai cleanup machine ID [options]",
    help="[Host] Remove all expired storage instances from the machine, freeing up space",
    epilog=deindent("""
        Instances expire on their end date. Expired instances still pay storage fees, but can not start.
        Since hosts are still paid storage fees for expired instances, we do not auto delete them.
        Instead you can use this CLI/API function to delete all expired storage instances for a machine.
        This is useful if you are running low on storage, want to do maintenance, or are subsidizing storage, etc.
    """)
)
def cleanup__machine(args):
    """
    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    cleanup_machine(args, args.id)


@parser.command(
   argument("id", help="id of machine to delete", type=int),
    usage="vastai delete machine <id>",
    help="[Host] Delete machine if the machine is not being used by clients. host jobs on their own machines are disregarded and machine is force deleted.",
) 
def delete__machine(args):
    """
    Deletes machine if the machine is not in use by clients. Disregards host jobs on their own machines and force deletes a machine.
    """
    req_url = apiurl(args, "/machines/{machine_id}/force_delete/".format(machine_id=args.id));
    r = http_post(args, req_url, headers=headers)
    if (r.status_code == 200):
        rj = r.json()
        if (rj["success"]):
            print("deleted machine_id ({machine_id}) and all related contracts.".format(machine_id=args.id));
        else:
            print(rj["msg"]);
    else:
        print(r.text);
        print("failed with error {r.status_code}".format(**locals()));


def list_machine(args, id):
    req_url = apiurl(args, "/machines/create_asks/")

    json_blob = {'machine': id, 'price_gpu': args.price_gpu,
                        'price_disk': args.price_disk, 'price_inetu': args.price_inetu, 'price_inetd': args.price_inetd, 'price_min_bid': args.price_min_bid, 
                        'min_chunk': args.min_chunk, 'end_date': string_to_unix_epoch(args.end_date), 'credit_discount_max': args.discount_rate, 'duration': args.duration}
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, req_url, headers=headers, json=json_blob)

    if (r.status_code == 200):
        rj = r.json()
        if (rj["success"]):
            price_gpu_ = str(args.price_gpu) if args.price_gpu is not None else "def"
            price_inetu_ = str(args.price_inetu)
            price_inetd_ = str(args.price_inetd)
            min_chunk_ = str(args.min_chunk)
            end_date_ = string_to_unix_epoch(args.end_date)
            discount_rate_ = str(args.discount_rate)
            duration_ = str(args.duration)
            if args.raw:
                return r
            else:
                print("offers created/updated for machine {id},  @ ${price_gpu_}/gpu/hr, ${price_inetu_}/GB up, ${price_inetd_}/GB down, {min_chunk_}/min gpus, max discount_rate {discount_rate_}, till {end_date_}, duration {duration_}".format(**locals()))
                num_extended = rj.get("extended", 0)

                if num_extended > 0:
                    print(f"extended {num_extended} client contracts to {args.end_date}")

        else:
            if args.raw:
                return r
            else:
                print(rj["msg"])
    else:
        print(r.text)
        print("failed with error {r.status_code}".format(**locals()))


@parser.command(
    argument("id", help="id of machine to list", type=int),
    argument("-g", "--price_gpu", help="per gpu rental price in $/hour  (price for active instances)", type=float),
    argument("-s", "--price_disk",
             help="storage price in $/GB/month (price for inactive instances), default: $0.15/GB/month", type=float),
    argument("-u", "--price_inetu", help="price for internet upload bandwidth in $/GB", type=float),
    argument("-d", "--price_inetd", help="price for internet download bandwidth in $/GB", type=float),
    argument("-b", "--price_min_bid", help="per gpu minimum bid price floor in $/hour", type=float),
    argument("-r", "--discount_rate", help="Max long term prepay discount rate fraction, default: 0.4 ", type=float),
    argument("-m", "--min_chunk", help="minimum amount of gpus", type=int),
    argument("-e", "--end_date", help="contract offer expiration - the available until date (optional, in unix float timestamp or MM/DD/YYYY format)", type=str),
    argument("-l", "--duration", help="Updates end_date daily to be duration from current date. Cannot be combined with end_date. Format is: `n days`, `n weeks`, `n months`, `n years`, or total intended duration in seconds."),
    usage="vastai list machine ID [options]",
    help="[Host] list a machine for rent",
    epilog=deindent("""
        Performs the same action as pressing the "LIST" button on the site https://cloud.vast.ai/host/machines.
        On the end date the listing will expire and your machine will unlist. However any existing client jobs will still remain until ended by their owners.
        Once you list your machine and it is rented, it is extremely important that you don't interfere with the machine in any way. 
        If your machine has an active client job and then goes offline, crashes, or has performance problems, this could permanently lower your reliability rating. 
        We strongly recommend you test the machine first and only list when ready.
    """)
)
def list__machine(args):
    """
    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    return list_machine(args, args.id)


@parser.command(
    argument("ids", help="ids of instance to list", type=int, nargs='+'),
    argument("-g", "--price_gpu", help="per gpu on-demand rental price in $/hour (base price for active instances)", type=float),
    argument("-s", "--price_disk",
             help="storage price in $/GB/month (price for inactive instances), default: $0.15/GB/month", type=float),
    argument("-u", "--price_inetu", help="price for internet upload bandwidth in $/GB", type=float),
    argument("-d", "--price_inetd", help="price for internet download bandwidth in $/GB", type=float),
    argument("-b", "--price_min_bid", help="per gpu minimum bid price floor in $/hour", type=float),
    argument("-r", "--discount_rate", help="Max long term prepay discount rate fraction, default: 0.4 ", type=float),
    argument("-m", "--min_chunk", help="minimum amount of gpus", type=int),
    argument("-e", "--end_date", help="contract offer expiration - the available until date (optional, in unix float timestamp or MM/DD/YYYY format)", type=str),
    argument("-l", "--duration", help="Updates end_date daily to be duration from current date. Cannot be combined with end_date. Format is: `n days`, `n weeks`, `n months`, `n years`, or total intended duration in seconds."),
    usage="vastai list machines IDs [options]",
    help="[Host] list machines for rent",
    epilog=deindent("""
        This variant can be used to list or update the listings for multiple machines at once with the same args.
        You could extend the end dates of all your machines using a command combo like this:
        ./vast.py list machines $(./vast.py show machines -q) -e 12/31/2024 --retry 6
    """)
)
def list__machines(args):
    """
    """
    return [list_machine(args, id) for id in args.ids]
    return res


@parser.command(
    argument("id", help="id of machine to list", type=int),
    argument("-p", "--price_disk",
             help="storage price in $/GB/month, default: $0.15/GB/month", default=.15, type=float),
    argument("-e", "--end_date", help="contract offer expiration - the available until date (optional, in unix float timestamp or MM/DD/YYYY format), default 1 month", type=str),
    argument("-s", "--size", help="size of disk space allocated to offer in GB, default 15 GB", default=15),
    usage="vastai list volume ID [options]",
    help="[Host] list disk space for rent as a volume on a machine",
    epilog=deindent("""
        Allocates a section of disk on a machine to be used for volumes.  
    """)
)
def list__volume(args):        
    size = args.size
    if not size:
        size = 15.0
    price_disk = args.price_disk
    if not price_disk:
        price_disk = .15

    json_blob ={
        "size": int(size),
        "machine": int(args.id)
    }
    if args.end_date:
        json_blob["end_date"] = string_to_unix_epoch(args.end_date)


    url = apiurl(args, "/volumes/")

    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_post(args, url,  headers=headers,json=json_blob)
    r.raise_for_status()
    if args.raw:
        return r
    else:
        print("Created. {}".format(r.json()))


@parser.command(
    argument("ids", help="id of machines list", type=int, nargs='+'),
    argument("-s", "--price_disk",
             help="storage price in $/GB/month, default: $0.10/GB/month", type=float),
    argument("-e", "--end_date", help="contract offer expiration - the available until date (optional, in unix float timestamp or MM/DD/YYYY format)", type=str),
    argument("-n", "--size", help="size of disk space allocated to offer in GB, default 5 GB"),
    usage="vastai list volume IDs [options]",
    help="[Host] list disk space for rent as a volume on machines",
    epilog=deindent("""
        Allocates a section of disk on machines to be used for volumes.  
    """)
)
def list__volumes(args):
    size = args.size
    if not size:
        size = 15.0
    price_disk = args.price_disk
    if not price_disk:
        price_disk = .15

    json_blob ={
        "size": int(size),
        "machine": [int(id) for id in args.ids]
    }
    if args.end_date:
        json_blob["end_date"] = string_to_unix_epoch(args.end_date)


    url = apiurl(args, "/volumes/")

    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_post(args, url,  headers=headers,json=json_blob)
    r.raise_for_status()
    if args.raw:
        return r
    else:
        print("Created. {}".format(r.json()))



@parser.command(
    argument("id", help="id of machine to remove default instance from", type=int),
    usage="vastai remove defjob id",
    help="[Host] Delete default jobs",
)
def remove__defjob(args):
    """


    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    req_url = apiurl(args, "/machines/{machine_id}/defjob/".format(machine_id=args.id));
    # print(req_url);
    r = http_del(args, req_url, headers=headers)

    if (r.status_code == 200):
        rj = r.json();
        if (rj["success"]):
            print("default instance for machine {machine_id} removed.".format(machine_id=args.id));
        else:
            print(rj["msg"]);
    else:
        print(r.text);
        print("failed with error {r.status_code}".format(**locals()));



def set_ask(args):
    """

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    print("set asks!\n");



@parser.command(
    argument("id", help="id of machine to launch default instance on", type=int),
    argument("--price_gpu", help="per gpu rental price in $/hour", type=float),
    argument("--price_inetu", help="price for internet upload bandwidth in $/GB", type=float),
    argument("--price_inetd", help="price for internet download bandwidth in $/GB", type=float),
    argument("--image", help="docker container image to launch", type=str),
    argument("--args", nargs=argparse.REMAINDER, help="list of arguments passed to container launch"),
    usage="vastai set defjob id [--api-key API_KEY] [--price_gpu PRICE_GPU] [--price_inetu PRICE_INETU] [--price_inetd PRICE_INETD] [--image IMAGE] [--args ...]",
    help="[Host] Create default jobs for a machine",
    epilog=deindent("""
        Performs the same action as creating a background job at https://cloud.vast.ai/host/create.       
                    
    """)
    
)
def set__defjob(args):
    """

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    req_url   = apiurl(args, "/machines/create_bids/");
    json_blob = {'machine': args.id, 'price_gpu': args.price_gpu, 'price_inetu': args.price_inetu, 'price_inetd': args.price_inetd, 'image': args.image, 'args': args.args}
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, req_url, headers=headers, json=json_blob)
    if (r.status_code == 200):
        rj = r.json();
        if (rj["success"]):
            print(
                "bids created for machine {args.id},  @ ${args.price_gpu}/gpu/day, ${args.price_inetu}/GB up, ${args.price_inetd}/GB down".format(**locals()));
        else:
            print(rj["msg"]);
    else:
        print(r.text);
        print("failed with error {r.status_code}".format(**locals()));


def smart_split(s, char):
    in_double_quotes = False
    in_single_quotes = False #note that isn't designed to work with nested quotes within the env
    parts = []
    current = []

    for c in s:
        if c == char and not (in_double_quotes or in_single_quotes):
            parts.append(''.join(current))
            current = []
        elif c == '\'':
            in_single_quotes = not in_single_quotes
            current.append(c)
        elif c == '\"':
            in_double_quotes = not in_double_quotes
            current.append(c)
        else:
            current.append(c)
    parts.append(''.join(current))  # add last part
    return parts



def parse_env(envs):
    result = {}
    if (envs is None):
        return result
    env = smart_split(envs,' ')
    prev = None
    for e in env:
        if (prev is None):
          if (e in {"-e", "-p", "-h", "-v"}):
              prev = e
          else:
            pass
        else:
          if (prev == "-p"):
            if set(e).issubset(set("0123456789:tcp/udp")):
                result["-p " + e] = "1"
            else:
                pass
          elif (prev == "-e"):
            kv = e.split('=')
            if len(kv) >= 2: #set(e).issubset(set("1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_=")):
                val = kv[1]
                if len(kv) > 2:
                    val = '='.join(kv[1:])
                result[kv[0]] = val.strip("'\"")
            else:
                pass
          elif (prev == "-v"):
            if (set(e).issubset(set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:./_"))):
                result["-v " + e] = "1" 
          else:
              result[prev] = e
          prev = None
    #print(result)
    return result


#print(parse_env("-e TYZ=BM3828 -e BOB=UTC -p 10831:22 -p 8080:8080"))



def pretty_print_POST(req):
    print('{}\n{}\r\n{}\r\n\r\n{}'.format(
        '-----------START-----------',
        req.method + ' ' + req.url,
        '\r\n'.join('{}: {}'.format(k, v) for k, v in req.headers.items()),
        req.body,
    ))


@parser.command(
    argument("id", help="id of machine to set min bid price for", type=int),
    argument("--price", help="per gpu min bid price in $/hour", type=float),
    usage="vastai set min_bid id [--price PRICE]",
    help="[Host] Set the minimum bid/rental price for a machine",
    epilog=deindent("""
        Change the current min bid price of machine id to PRICE.
    """),
)
def set__min_bid(args):
    """

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    url = apiurl(args, "/machines/{id}/minbid/".format(id=args.id))
    json_blob = {"client_id": "me", "price": args.price,}
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, url,  headers=headers,json=json_blob)
    r.raise_for_status()
    print("Per gpu min bid price changed".format(r.json()))


@parser.command(
    argument("id", help="id of machine to schedule maintenance for", type=int),
    argument("--sdate",      help="maintenance start date in unix epoch time (UTC seconds)", type=float),
    argument("--duration",   help="maintenance duration in hours", type=float),
    argument("--maintenance_reason",   help="(optional) reason for the maintenance. Minimum 70 chars and Maximum 300 chars", type=str, default="not provided"),
    argument("--maintenance_category",   help="(optional) can be one of [power, internet, disk, gpu, software, other]", type=str, default="not provided"),
    usage="vastai schedule maintenance id [--sdate START_DATE --duration DURATION --maintenance_reason MAINTENANCE_REASON --maintenance_category MAINTENANCE_CATEGORY]",
    help="[Host] Schedule upcoming maint window",
    epilog=deindent("""
        The proper way to perform maintenance on your machine is to wait until all active contracts have expired or the machine is vacant.
        For unplanned or unscheduled maintenance, use this schedule maint command. That will notify the client that you have to take the machine down and that they should save their work. 
        You can specify a date, duration, reason and category for the maintenance.         

        Example: vastai schedule maint 8207 --sdate 1677562671 --duration 0.5 --maintenance_reason "maintenance reason as a string that briefly helps clients understand why the maintenance was necessary" --maintenance_category "power"
    """),
    )
def schedule__maint(args):
    """
    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    url = apiurl(args, "/machines/{id}/dnotify/".format(id=args.id))

    dt = datetime.utcfromtimestamp(args.sdate)
    print(f"Scheduling maintenance window starting {dt} lasting {args.duration} hours")
    print(f"This will notify all clients of this machine.")
    ok = input("Continue? [y/n] ")
    if ok.strip().lower() != "y":
        return

    json_blob = {"client_id": "me", "sdate": string_to_unix_epoch(args.sdate), "duration": args.duration, "maintenance_reason": args.maintenance_reason, "maintenance_category": args.maintenance_category}
    if (args.explain):
        print("request json: ")
        print(json_blob)
    r = http_put(args, url,  headers=headers,json=json_blob)
    r.raise_for_status()
    print(f"Maintenance window scheduled for {dt} success".format(r.json()))

@parser.command(
    argument("Machine", help="id of machine to display", type=int),
    argument("-q", "--quiet", action="store_true", help="only display numeric ids"),
    usage="vastai show machine ID [OPTIONS]",
    help="[Host] Show hosted machines",
)
def show__machine(args):
    """
    Show a machine the host is offering for rent.

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    req_url = apiurl(args, f"/machines/{args.Machine}", {"owner": "me"});
    r = http_get(args, req_url)
    r.raise_for_status()
    rows = r.json()
    if args.raw:
        return r
    else:
        if args.quiet:
            ids = [f"{row['id']}" for row in rows]
            print(" ".join(id for id in ids))
        else:
            display_table(rows, machine_fields)


@parser.command(
    argument("-q", "--quiet", action="store_true", help="only display numeric ids"),
    usage="vastai show machines [OPTIONS]",
    help="[Host] Show hosted machines",
)
def show__machines(args):
    """
    Show the machines user is offering for rent.

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    req_url = apiurl(args, "/machines", {"owner": "me"});
    r = http_get(args, req_url)
    r.raise_for_status()
    rows = r.json()["machines"]
    if args.raw:
        return r
    else:
        if args.quiet:            
            ids = [f"{row['id']}" for row in rows]
            print(" ".join(id for id in ids))
        else:
            display_table(rows, machine_fields)


@parser.command(
    argument("-ids", help="comma seperated string of machine_ids for which to get maintenance information", type=str),
    argument("-q", "--quiet", action="store_true", help="only display numeric ids of the machines in maintenance"),
    usage="\nvastai show maints -ids 'machine_id_1' [OPTIONS]\nvastai show maints -ids 'machine_id_1, machine_id_2' [OPTIONS]",
    help="[Host] Show maintenance information for host machines",
)
def show__maints(args):
    """
    Show the maintenance information for the machines

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    machine_ids = args.ids.split(',')
    machine_ids = list(map(int, machine_ids))

    req_url = apiurl(args, "/machines/maintenances", {"owner": "me", "machine_ids" : machine_ids});
    r = http_get(args, req_url)
    r.raise_for_status()
    rows = r.json()
    if args.raw:
        return r
    else:
        if args.quiet:   
            ids = [f"{row['machine_id']}" for row in rows]
            print(" ".join(id for id in ids))
        else:
            display_table(rows, maintenance_fields)


@parser.command(
    argument("id", help="id of machine to unlist", type=int),
    usage="vastai unlist machine <id>",
    help="[Host] Unlist a listed machine",
)

def unlist__machine(args):
    """
    Removes machine from list of machines for rent.

    :param argparse.Namespace args: should supply all the command-line options
    :rtype:
    """
    req_url = apiurl(args, "/machines/{machine_id}/asks/".format(machine_id=args.id));
    r = http_del(args, req_url, headers=headers)
    if (r.status_code == 200):
        rj = r.json();
        if (rj["success"]):
            print("all offers for machine {machine_id} removed, machine delisted.".format(machine_id=args.id));
        else:
            print(rj["msg"]);
    else:
        print(r.text);
        print("failed with error {r.status_code}".format(**locals()));


def suppress_stdout():
    """
    A context manager to suppress standard output (stdout) within its block.

    This is useful for silencing output from functions or blocks of code that 
    print to stdout, especially when such output is not needed or should be 
    hidden from the user.

    Usage:
        with suppress_stdout():
            # Code block with suppressed stdout
            some_function_that_prints()

    Yields:
        None
    """
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout

def destroy_instance_silent(id, args):
    """
    Silently destroys a specified instance, retrying up to three times if it fails.

    This function calls the `destroy_instance` function to terminate an instance.
    If the `args.raw` flag is set to True, the output of the destruction process
    is suppressed to keep the console output clean.

    Args:
        id (str): The ID of the instance to destroy.
        args (argparse.Namespace): Command-line arguments containing necessary flags.

    Returns:
        dict: A dictionary with a success status and error message, if any.
    """
    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            # Suppress output if args.raw is True
            if args.raw:
                with open(os.devnull, 'w') as devnull, redirect_stdout(devnull), redirect_stderr(devnull):
                    destroy_instance(id, args)
            else:
                destroy_instance(id, args)

            # If successful, exit the loop and return success
            if not args.raw:
                print(f"Instance {id} destroyed successfully on attempt {attempt}.")
            return {"success": True}

        except Exception as e:
            if not args.raw:
                print(f"Error destroying instance {id}: {e}")

        # Wait before retrying if the attempt failed
        if attempt < max_retries:
            if not args.raw:
                print(f"Retrying in 10 seconds... (Attempt {attempt}/{max_retries})")
            time.sleep(10)
        else:
            if not args.raw:
                print(f"Failed to destroy instance {id} after {max_retries} attempts.")
            return {"success": False, "error": "Max retries exceeded"}


def progress_print(args, *args_to_print):
    """
    Prints progress messages to the console based on the `raw` flag.

    This function ensures that progress messages are only printed when the `raw`
    output mode is not enabled. This is useful for controlling the verbosity of
    the script's output, especially in machine-readable formats.

    Args:
        args (argparse.Namespace): Parsed command-line arguments containing flags
                                  and options such as `raw`.
        *args_to_print: Variable length argument list of messages to print.

    Returns:
        None
    """
    if not args.raw:
        print(*args_to_print)

def debug_print(args, *args_to_print):
    """
    Prints debug messages to the console based on the `debugging` and `raw` flags.

    This function ensures that debug messages are only printed when debugging is
    enabled and the `raw` output mode is not active. It helps in providing detailed
    logs for troubleshooting without cluttering the standard output during normal
    operation.

    Args:
        args (argparse.Namespace): Parsed command-line arguments containing flags
                                  and options such as `debugging` and `raw`.
        *args_to_print: Variable length argument list of debug messages to print.

    Returns:
        None
    """
    if args.debugging and not args.raw:
        print(*args_to_print)

def instance_exist(instance_id, api_key, args):
    if not hasattr(args, 'debugging'):
        args.debugging = False

    if not instance_id:
        return False

    show_args = argparse.Namespace(
        id=instance_id,
        api_key=api_key,
        url=args.url,
        retry=args.retry,
        explain=False,
        raw=True,
        debugging=args.debugging
    )
    try:
        instance_info = show__instance(show_args)
        
        # Empty list or None means instance doesn't exist - return False without error
        if not instance_info:
            return False

        # If we have instance info, check its status
        status = instance_info.get('intended_status') or instance_info.get('actual_status')
        if status in ['destroyed', 'terminated', 'offline']:
            return False

        return True

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            # Instance does not exist
            return False
        else:
            if args.debugging:
                debug_print(args, f"HTTPError when checking instance existence: {e}")
            return False
    except Exception as e:
        if args.debugging:
            debug_print(args, f"No instance found or Unexpected error checking instance existence: {e}")
        return False
    
def run_machinetester(ip_address, port, instance_id, machine_id, delay, args, api_key=None):
    """
    Executes machine testing by connecting to the specified IP and port, monitoring
    the instance's status, and handling test completion or failures.

    This function performs the following steps:
        1. Disables SSL warnings.
        2. Optionally delays the start of testing.
        3. Continuously checks the instance status and attempts to connect to the
           `/progress` endpoint to monitor test progress.
        4. Handles different response messages, such as completion or errors.
        5. Implements timeout logic to prevent indefinite waiting.
        6. Ensures instance cleanup in case of failures or completion.

    Args:
        ip_address (str): The public IP address of the instance to test.
        port (int): The port number to connect to for testing.
        instance_id (str): The ID of the instance being tested.
        machine_id (str): The machine ID associated with the instance.
        delay (int): The number of seconds to delay before starting the test.
        args (argparse.Namespace): Parsed command-line arguments containing flags
                                  and options such as `debugging` and `raw`.
        api_key (str, optional): API key for authentication. Defaults to None.

    Returns:
        tuple:
            - bool: `True` if the test was successful, `False` otherwise.
            - str: Reason for failure if the test was not successful, empty string otherwise.
    """

    # Temporarily disable SSL warnings
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    delay = int(delay)

    # Ensure debugging is set in args
    if not hasattr(args, 'debugging'):
        args.debugging = False

    def is_instance(instance_id):
        """Check instance status via show__instance."""
        show_args = argparse.Namespace(
            id=instance_id,
            explain=False,
            api_key=api_key,
            url="https://console.vast.ai",
            retry=3,
            raw=True,
            debugging=args.debugging,
        )
        try:
            instance_info = show__instance(show_args)
            if args.debugging:
                debug_print(args, f"is_instance(): Output from vast show instance: {instance_info}")

            if not instance_info or not isinstance(instance_info, dict):
                if args.debugging:
                    debug_print(args, "is_instance(): No valid instance information received.")
                return 'unknown'

            actual_status = instance_info.get('actual_status', 'unknown')
            return actual_status if actual_status in ['running', 'offline', 'exited', 'created'] else 'unknown'
        except Exception as e:
            if args.debugging:
                debug_print(args, f"is_instance(): Error: {e}")
            return 'unknown'

    # Prepare destroy_args with required attributes set to False as needed
    destroy_args = argparse.Namespace(api_key=api_key, url="https://console.vast.ai", retry=3, explain=False, raw=args.raw, debbuging=args.debugging,)

    # Delay start if specified
    if delay > 0:
        if args.debugging:
            debug_print(args, f"Sleeping for {delay} seconds before starting tests.")
        time.sleep(delay)

    start_time = time.time()
    no_response_seconds = 0
    printed_lines = set()
    first_connection_established = False  # Flag to track first successful connection
    instance_destroyed = False  # Track whether the instance has been destroyed
    try:
        while time.time() - start_time < 600:
            # Check instance status with high priority for offline status
            status = is_instance(instance_id)
            if args.debugging:
                debug_print(args, f"Instance {instance_id} status: {status}")
                
            if status == 'offline':
                reason = "Instance offline during testing"
                progress_print(args, f"Instance {instance_id} went offline. {reason}")
                destroy_instance_silent(instance_id, destroy_args)
                instance_destroyed = True
                with open("Error_testresults.log", "a") as f:
                    f.write(f"{machine_id}:{instance_id} {reason}\n")
                return False, reason

            # Attempt to connect to the progress endpoint
            try:
                if args.debugging:
                    debug_print(args, f"Sending GET request to https://{ip_address}:{port}/progress")
                response = requests.get(f'https://{ip_address}:{port}/progress', verify=False, timeout=10)
                
                if response.status_code == 200 and not first_connection_established:
                    progress_print(args, "Successfully established HTTPS connection to the server.")
                    first_connection_established = True

                message = response.text.strip()
                if args.debugging:
                    debug_print(args, f"Received message: '{message}'")
            except requests.exceptions.RequestException as e:
                if args.debugging:
                    progress_print(args, f"Error making HTTPS request: {e}")
                message = ''

            # Process response messages
            if message:
                lines = message.split('\n')
                new_lines = [line for line in lines if line not in printed_lines]
                for line in new_lines:
                    if line == 'DONE':
                        progress_print(args, "Test completed successfully.")
                        with open("Pass_testresults.log", "a") as f:
                            f.write(f"{machine_id}\n")
                        progress_print(args, f"Test passed.")
                        destroy_instance_silent(instance_id, destroy_args)
                        instance_destroyed = True
                        return True, ""
                    elif line.startswith('ERROR'):
                        progress_print(args, line)
                        with open("Error_testresults.log", "a") as f:
                            f.write(f"{machine_id}:{instance_id} {line}\n")
                        progress_print(args, f"Test failed with error: {line}.")
                        destroy_instance_silent(instance_id, destroy_args)
                        instance_destroyed = True
                        return False, line
                    else:
                        progress_print(args, line)
                    printed_lines.add(line)
                no_response_seconds = 0
            else:
                no_response_seconds += 20
                if args.debugging:
                    debug_print(args, f"No message received. Incremented no_response_seconds to {no_response_seconds}.")

            if status == 'running' and no_response_seconds >= 120:
                with open("Error_testresults.log", "a") as f:
                    f.write(f"{machine_id}:{instance_id} No response from port {port} for 120s with running instance\n")
                progress_print(args, f"No response for 120s with running instance. This may indicate a misconfiguration of ports on the machine. Network error or system stall or crashed. ")
                destroy_instance_silent(instance_id, destroy_args)
                instance_destroyed = True
                return False, "No response for 120 seconds with running instance. The system might have crashed or stalled during stress test. Use the self-test machine function in vast cli"

            if args.debugging:
                debug_print(args, "Waiting for 20 seconds before the next check.")
            time.sleep(20)

        if args.debugging:
            debug_print(args, f"Time limit reached. Destroying instance {instance_id}.")
        return False, "Test did not complete within the time limit"
    finally:
        # Ensure instance cleanup
        if not instance_destroyed and instance_id and instance_exist(instance_id, api_key, destroy_args):
           destroy_instance_silent(instance_id, destroy_args)
        progress_print(args, f"Machine: {machine_id} Done with testing remote.py results {message}")
        warnings.simplefilter('default')

def safe_float(value):
    """
    Convert value to float, returning 0 if value is None.
    
    Args:
        value: The value to convert to float
        
    Returns:
        float: The converted value, or 0 if value is None
    """
    if value is None:
        return 0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0

def check_requirements(machine_id, api_key, args):
    """
    Validates whether a machine meets the specified hardware and performance requirements.

    This function queries the machine's offers and checks various criteria such as CUDA
    version, reliability, port count, PCIe bandwidth, internet speeds, GPU RAM, system
    RAM, and CPU cores relative to the number of GPUs. If any of these requirements are
    not met, it records the reasons for the failure.

    Args:
        machine_id (str): The ID of the machine to check.
        api_key (str): API key for authentication with the VAST API.
        args (argparse.Namespace): Parsed command-line arguments containing flags
                                  and options such as `debugging` and `raw`.

    Returns:
        tuple:
            - bool: `True` if the machine meets all requirements, `False` otherwise.
            - list: A list of reasons why the machine does not meet the requirements.
    """
    unmet_reasons = []

    # Prepare search arguments to get machine offers
    search_args = argparse.Namespace(
        query=[f"machine_id={machine_id}", "verified=any", "rentable=true", "rented=any"],
        type="on-demand",
        quiet=False,
        no_default=False,
        new=False,
        limit=None,
        disable_bundling=False,
        storage=5.0,
        order="score-",
        raw=True,  # Ensure raw output to get data directly
        explain=args.explain,
        api_key=api_key,
        url=args.url,
        retry=args.retry
    )

    try:
        # Call search__offers and capture the return value directly
        offers = search__offers(search_args)
        if args.debugging:
            debug_print(args, "Captured offers from search__offers:", offers)

        if not offers:
            unmet_reasons.append(f"Machine ID {machine_id} not found or not rentable.")
            progress_print(args, f"Machine ID {machine_id} not found or not rentable.")
            return False, unmet_reasons

        # Sort offers based on 'dlperf' in descending order
        sorted_offers = sorted(offers, key=lambda x: x.get('dlperf', 0), reverse=True)
        top_offer = sorted_offers[0]

        if args.debugging:
            debug_print(args, "Top offer found:", top_offer)

        # Requirement checks
        # 1. CUDA version
        if safe_float(top_offer.get('cuda_max_good')) < 11.8:
            unmet_reasons.append("CUDA version < 11.8")

        # 2. Reliability
        if safe_float(top_offer.get('reliability')) <= 0.90:
            unmet_reasons.append("Reliability <= 0.90")

        # 3. Direct port count
        if safe_float(top_offer.get('direct_port_count')) <= 3:
            unmet_reasons.append("Direct port count <= 3")

        # 4. PCIe bandwidth
        if safe_float(top_offer.get('pcie_bw')) <= 2.85:
            unmet_reasons.append("PCIe bandwidth <= 2.85")

        # 5. Download speed
        if safe_float(top_offer.get('inet_down')) <= 10:
            unmet_reasons.append("Download speed <= 10 Mb/s")

        # 6. Upload speed
        if safe_float(top_offer.get('inet_up')) <= 10:
            unmet_reasons.append("Upload speed <= 10 Mb/s")

        # 7. GPU RAM
        if safe_float(top_offer.get('gpu_ram')) <= 7:
            unmet_reasons.append("GPU RAM <= 7 GB")

        # Additional Requirement Checks

        # 8. System RAM vs. Total GPU RAM
        gpu_total_ram = safe_float(top_offer.get('gpu_total_ram'))  # in MB
        cpu_ram = safe_float(top_offer.get('cpu_ram'))  # in MB
        if cpu_ram < gpu_total_ram:
            unmet_reasons.append("System RAM is less than total VRAM.")

        # Debugging Information for RAM
        if args.debugging:
            debug_print(args, f"CPU RAM: {cpu_ram} MB")
            debug_print(args, f"Total GPU RAM: {gpu_total_ram} MB")

        # 9. CPU Cores vs. Number of GPUs
        cpu_cores = int(safe_float(top_offer.get('cpu_cores')))
        num_gpus = int(safe_float(top_offer.get('num_gpus')))
        if cpu_cores < 2 * num_gpus:
            unmet_reasons.append("Number of CPU cores is less than twice the number of GPUs.")

        # Debugging Information for CPU Cores
        if args.debugging:
            debug_print(args, f"CPU Cores: {cpu_cores}")
            debug_print(args, f"Number of GPUs: {num_gpus}")

        # Return True if all requirements are met, False otherwise
        if unmet_reasons:
            progress_print(args, f"Machine ID {machine_id} does not meet the requirements:")
            for reason in unmet_reasons:
                progress_print(args, f"- {reason}")
            return False, unmet_reasons
        else:
            progress_print(args, f"Machine ID {machine_id} meets all the requirements.")
            return True, []

    except Exception as e:
        progress_print(args, f"An unexpected error occurred: {str(e)}")
        if args.debugging:
            debug_print(args, f"Exception details: {e}")
        return False, [f"Unexpected error: {str(e)}"]


def wait_for_instance(instance_id, api_key, args, destroy_args, timeout=900, interval=10):
    """
    Waits for an instance to reach a running state and monitors its status for errors.

    """

    if not hasattr(args, 'debugging'):
        args.debugging = False

    start_time = time.time()
    show_args = argparse.Namespace(
        id=instance_id,
        quiet=False,
        raw=True,  # Ensure raw output to get data directly
        explain=args.explain,
        api_key=api_key,
        url=args.url,
        retry=args.retry,
        debugging=args.debugging,
    )
    
    if args.debugging:
        debug_print(args, "Starting wait_for_instance with ID:", instance_id)
    
    while time.time() - start_time < timeout:
        try:
            # Directly call show__instance and capture the return value
            instance_info = show__instance(show_args)
            
            if not instance_info:
                progress_print(args, f"No information returned for instance {instance_id}. Retrying...")
                time.sleep(interval)
                continue  # Retry

            # Check for error in status_msg
            status_msg = instance_info.get('status_msg', '')
            if status_msg and 'Error' in status_msg:
                reason = f"Instance {instance_id} encountered an error: {status_msg.strip()}"
                progress_print(args, reason)
                
                # Destroy the instance
                if instance_exist(instance_id, api_key, destroy_args):
                    destroy_instance_silent(instance_id, destroy_args)
                    progress_print(args, f"Instance {instance_id} has been destroyed due to error.")
                else:
                    progress_print(args, f"Instance {instance_id} could not be destroyed or does not exist.")
                
                return False, reason
            
            # Check if instance went offline
            actual_status = instance_info.get('actual_status', 'unknown')
            if actual_status == 'offline':
                reason = "Instance offline during testing"
                progress_print(args, reason)
                
                # Destroy the instance
                if instance_exist(instance_id, api_key, destroy_args):
                    destroy_instance_silent(instance_id, destroy_args)
                    progress_print(args, f"Instance {instance_id} has been destroyed due to being offline.")
                else:
                    progress_print(args, f"Instance {instance_id} could not be destroyed or does not exist.")
                
                return False, reason
            
            # Check if instance is running
            if instance_info.get('intended_status') == 'running' and actual_status == 'running':
                if args.debugging:
                    debug_print(args, f"Instance {instance_id} is now running.")
                return instance_info, None  # Return instance_info with None for reason
            
            # Print feedback about the current status
            progress_print(args, f"Instance {instance_id} status: {actual_status}... waiting for 'running' status.")
            time.sleep(interval)
        
        except Exception as e:
            progress_print(args, f"Error retrieving instance info for {instance_id}: {e}. Retrying...")
            if args.debugging:
                debug_print(args, f"Exception details: {str(e)}")
            time.sleep(interval)
    
    # Timeout reached without instance running
    reason = f"Instance did not become running within {timeout} seconds. Verify network configuration. Use the self-test machine function in vast cli"
    progress_print(args, reason)
    return False, reason

@parser.command(
    argument("machine_id", help="Machine ID", type=str),
    argument("--debugging", action="store_true", help="Enable debugging output"),
    argument("--explain", action="store_true", help="Output verbose explanation of mapping of CLI calls to HTTPS API endpoints"),
    argument("--raw", action="store_true", help="Output machine-readable JSON"), 
    argument("--url", help="Server REST API URL", default="https://console.vast.ai"),
    argument("--retry", help="Retry limit", type=int, default=3),
    argument("--ignore-requirements", action="store_true", help="Ignore the minimum system requirements and run the self test regardless"),
    usage="vastai self-test machine <machine_id> [--debugging] [--explain] [--api_key API_KEY] [--url URL] [--retry RETRY] [--raw] [--ignore-requirements]",
    help="[Host] Perform a self-test on the specified machine",
    epilog=deindent("""
        This command tests if a machine meets specific requirements and 
        runs a series of tests to ensure it's functioning correctly.

        Examples:
         vast self-test machine 12345
         vast self-test machine 12345 --debugging
         vast self-test machine 12345 --explain
         vast self-test machine 12345 --api_key <YOUR_API_KEY>
    """),
)

def self_test__machine(args):
    """
    Performs a self-test on the specified machine to verify its compliance with
    required specifications and functionality.
    """
    instance_id = None  # Store instance ID for cleanup if needed
    result = {"success": False, "reason": ""}
    
    # Ensure debugging attribute exists in args
    if not hasattr(args, 'debugging'):
        args.debugging = False
    
    try:
        # Load API key
        if not args.api_key:
            api_key_file = os.path.expanduser("~/.vast_api_key")
            if os.path.exists(api_key_file):
                with open(api_key_file, "r") as reader:
                    args.api_key = reader.read().strip()
            else:
                progress_print(args, "No API key found. Please set it using 'vast set api-key YOUR_API_KEY_HERE'")
                result["reason"] = "API key not found."
        
        api_key = args.api_key
        if not api_key:
            raise Exception("API key is missing.")

        # Prepare destroy_args
        destroy_args = argparse.Namespace(
            api_key=api_key,
            url=args.url,
            retry=args.retry,
            explain=False,
            raw=args.raw,
            debugging=args.debugging,
        )

        # Check requirements
        meets_requirements, unmet_reasons = check_requirements(args.machine_id, api_key, args)
        if not meets_requirements and not args.ignore_requirements:
            # immediately fail
            progress_print(args, f"Machine ID {args.machine_id} does not meet the following requirements:")
            for reason in unmet_reasons:
                progress_print(args, f"- {reason}")
            result["reason"] = "; ".join(unmet_reasons)
            return result
        if not meets_requirements and args.ignore_requirements:
            progress_print(args, f"Machine ID {args.machine_id} does not meet the following requirements:")
            for reason in unmet_reasons:
                progress_print(args, f"- {reason}")
                # If user did pass --ignore-requirements, warn and continue
                progress_print(args, "Continuing despite unmet requirements because --ignore-requirements is set.")

        def cuda_map_to_image(cuda_version):
            """
            Maps a CUDA version to a Docker image tag, falling back to the next lower version until failure.
            """
            docker_repo = "vastai/test"
            # Convert float input to string
            if isinstance(cuda_version, float):
                cuda_version = str(cuda_version)
            
            # Predefined mapping. Tracks PyTorch releases
            docker_tag_map = {
                "11.8": "cu118",
                "12.1": "cu121",
                "12.4": "cu124",
                "12.6": "cu126",
                "12.8": "cu128"
            }
            
            if cuda_version in docker_tag_map:
                return f"{docker_repo}:self-test-{docker_tag_map[cuda_version]}"
            
            # Try to find the next version down
            cuda_float = float(cuda_version)
            
            # Try to decrement the version by 0.1 until we find a match or run out of options
            next_version = round(cuda_float - 0.1, 1)
            while next_version >= min(float(v) for v in docker_tag_map.keys()):
                next_version_str = str(next_version)
                if next_version_str in docker_tag_map:
                    return f"{docker_repo}:self-test-{docker_tag_map[next_version_str]}"
                next_version = round(next_version - 0.1, 1)
            
            raise KeyError(f"No CUDA version found for {cuda_version} or any lower version")
    

        def search_offers_and_get_top(machine_id):
            search_args = argparse.Namespace(
                query=[f"machine_id={machine_id}", "verified=any", "rentable=true", "rented=any"],
                type="on-demand",
                quiet=False,
                no_default=False,
                new=False,
                limit=None,
                disable_bundling=False,
                storage=5.0,
                order="score-",
                raw=True,
                explain=args.explain,
                api_key=api_key,
                url=args.url,
                retry=args.retry,
                debugging=args.debugging,
            )
            offers = search__offers(search_args)
            if not offers:
                progress_print(args, f"Machine ID {machine_id} not found or not rentable.")
                return None
            sorted_offers = sorted(offers, key=lambda x: x.get("dlperf", 0), reverse=True)
            return sorted_offers[0] if sorted_offers else None

        top_offer = search_offers_and_get_top(args.machine_id)
        if not top_offer:
            progress_print(args, f"No valid offers found for Machine ID {args.machine_id}")
            result["reason"] = "No valid offers found."
        else:
            ask_contract_id = top_offer["id"]
            cuda_version = top_offer["cuda_max_good"]
            docker_image = cuda_map_to_image(cuda_version)

            # Prepare arguments for instance creation
            create_args = argparse.Namespace(
                id=ask_contract_id,
                user=None,
                price=None,  # Set bid_price to None
                disk=40,  # Match the disk size from the working command
                image=docker_image,
                login=None,
                label=None,
                onstart=None,
                onstart_cmd="/verification/remote.sh",
                entrypoint=None,
                ssh=False,  # Set ssh to False
                jupyter=True,  # Set jupyter to True
                direct=True,
                jupyter_dir=None,
                jupyter_lab=False,
                lang_utf8=False,
                python_utf8=False,
                extra=None,
                env="-e TZ=PDT -e XNAME=XX4 -p 5000:5000 -p 1234:1234",
                args=None,
                force=False,
                cancel_unavail=False,
                template_hash=None,
                raw=True,
                explain=args.explain,
                api_key=api_key,
                url=args.url,
                retry=args.retry,
                debugging=args.debugging,
                bid_price=None,  # Ensure bid_price is None
            )

            # Create instance
            try:
                progress_print(args, f"Starting test with {docker_image}")
                response = create__instance(create_args)
                if isinstance(response, requests.Response):  # Check if it's an HTTP response
                    if response.status_code == 200:
                        try:
                            instance_info = response.json()  # Parse JSON
                            if args.debugging:
                                debug_print(args, "Captured instance_info from create__instance:", instance_info)
                        except json.JSONDecodeError as e:
                            progress_print(args, f"Error parsing JSON response: {e}")
                            debug_print(args, f"Raw response content: {response.text}")
                            raise Exception("Failed to parse JSON from instance creation response.")
                    else:
                        progress_print(args, f"HTTP error during instance creation: {response.status_code}")
                        debug_print(args, f"Response text: {response.text}")
                        raise Exception(f"Instance creation failed with status {response.status_code}")
                else:
                    raise Exception("Unexpected response type from create__instance.")
            except Exception as e:
                progress_print(args, f"Error creating instance: {e}")
                result["reason"] = "Failed to create instance. Check the docker configuration. Use the self-test machine function in vast cli "
                return result  # Cleanup handled in finally block

            # Extract instance ID and proceed
            instance_id = instance_info.get("new_contract")
            if not instance_id:
                progress_print(args, "Instance creation response did not contain 'new_contract'.")
                result["reason"] = "Instance creation failed."
            else:
                # Wait for the instance to start
                instance_info, wait_reason = wait_for_instance(instance_id, api_key, args, destroy_args)
                if not instance_info:
                    result["reason"] = wait_reason
                else:
                    # Proceed with the rest of your code
                    # Run machine tester
                    ip_address = instance_info.get("public_ipaddr")
                    if not ip_address:
                        result["reason"] = "Failed to retrieve public IP address."
                    else:
                        port_mappings = instance_info.get("ports", {}).get("5000/tcp", [])
                        port = port_mappings[0].get("HostPort") if port_mappings else None
                        if not port:
                            result["reason"] = "Failed to retrieve mapped port."
                        else:
                            delay = "15"
                            success, reason = run_machinetester(
                                ip_address, port, str(instance_id), args.machine_id, delay, args, api_key=api_key
                            )
                            result["success"] = success
                            result["reason"] = reason

    except Exception as e:
        result["success"] = False
        result["reason"] = str(e)

    finally:
        try:
            if instance_id and instance_exist(instance_id, api_key, destroy_args):
                destroy_instance_silent(instance_id, destroy_args)
        except Exception as e:
            if args.debugging:
                debug_print(args, f"Error during cleanup: {e}")

    # Output results
    if args.raw:
        print(json.dumps(result))
        sys.exit(0)
    else:
        if result["success"]:
            print("Test completed successfully.")
            sys.exit(0)
        else:
            print(f"Test failed: {result['reason']}")
            sys.exit(1)


login_deprecated_message = """


login via the command line is no longer supported.
go to https://console.vast.ai/cli in a web browser to get your api key, then run:

    vast set api-key YOUR_API_KEY_HERE
"""

"""
@parser.command(
    argument("ignored", nargs="*"),
    usage=login_deprecated_message
)
def create__account(args):
    print(login_deprecated_message)

@parser.command(
    argument("ignored", nargs="*"),
    usage=login_deprecated_message,
)
def login(args):
    print(login_deprecated_message)
"""
try:
  class MyAutocomplete(argcomplete.CompletionFinder):
    def quote_completions(self, completions: List[str], cword_prequote: str, last_wordbreak_pos: Optional[int]) -> List[str]:
      pre = super().quote_completions(completions, cword_prequote, last_wordbreak_pos)
      # preference the non-hyphenated options first
      return sorted(pre, key=lambda x: x.startswith('-'))
except:
  pass


def main():
    global ARGS
    parser.add_argument("--url", help="server REST api url", default=server_url_default)
    parser.add_argument("--retry", help="retry limit", default=3)
    parser.add_argument("--raw", action="store_true", help="output machine-readable json")
    parser.add_argument("--explain", action="store_true", help="output verbose explanation of mapping of CLI calls to HTTPS API endpoints")
    parser.add_argument("--api-key", help="api key. defaults to using the one stored in {}".format(APIKEY_FILE), type=str, required=False, default=os.getenv("VAST_API_KEY", api_key_guard))
    parser.add_argument("--version", help="show version", action="version", version=VERSION)

    ARGS = args = parser.parse_args()
    #print(args.api_key)
    if args.api_key is api_key_guard:
        if args.explain:
            print(f'checking {APIKEY_FILE}')
        if os.path.exists(APIKEY_FILE):
            if args.explain:
                print(f'reading key from {APIKEY_FILE}')
            with open(APIKEY_FILE, "r") as reader:
                args.api_key = reader.read().strip()
        else:
            args.api_key = None
    if args.api_key:
        headers["Authorization"] = "Bearer " + args.api_key

    try:
        check_for_update()
    except Exception as e:
        print(f"Error checking for update: {e}")

    if TABCOMPLETE:
        myautocc = MyAutocomplete()
        myautocc(parser.parser)

    try:
        res = args.func(args)
        if args.raw:
            # There's two types of responses right now
            try:
                print(json.dumps(res, indent=1, sort_keys=True))
            except:
                print(json.dumps(res.json(), indent=1, sort_keys=True))
            sys.exit(0)
        sys.exit(res)
    except requests.exceptions.HTTPError as e:
        try:
            errmsg = e.response.json().get("msg");
        except JSONDecodeError:
            if e.response.status_code == 401:
                errmsg = "Please log in or sign up"
            else:
                errmsg = "(no detail message supplied)"
        print("failed with error {e.response.status_code}: {errmsg}".format(**locals()));
    except ValueError as e:
      print(e)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, BrokenPipeError):
        pass
