"""Shared utility functions for the Vast.ai SDK and CLI.

Generic helpers that are not specific to any single layer (CLI, API, SDK).
"""

import re
import sys
import time
import math
import argparse
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------

def parse_version(version: str) -> tuple:
    parts = version.split(".")

    if len(parts) < 3:
        print(f"Invalid version format: {version}", file=sys.stderr)

    return tuple(int(part) for part in parts)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_seconds(value):
    """Validate that the input value is a valid number for seconds between yesterday and Jan 1, 2100."""
    try:
        val = int(value)

        # Calculate min_seconds as the start of yesterday in seconds
        yesterday = datetime.now() - timedelta(days=1)
        min_seconds = int(yesterday.timestamp())

        # Calculate max_seconds for Jan 1st, 2100 in seconds
        max_date = datetime(2100, 1, 1, 0, 0, 0)
        max_seconds = int(max_date.timestamp())

        if not (min_seconds <= val <= max_seconds):
            raise argparse.ArgumentTypeError(f"{value} is not a valid second timestamp.")
        return val
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value} is not a valid integer.")


# ---------------------------------------------------------------------------
# VRL (Vast Resource Locator) parsing
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# String / environment parsing
# ---------------------------------------------------------------------------

def smart_split(s, char):
    in_double_quotes = False
    in_single_quotes = False  # note that isn't designed to work with nested quotes within the env
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
    env = smart_split(envs, ' ')
    prev = None
    for e in env:
        if (prev is None):
            if (e in {"-e", "-p", "-h", "-v", "-n"}):
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
                if len(kv) >= 2:
                    val = kv[1]
                    if len(kv) > 2:
                        val = '='.join(kv[1:])
                    result[kv[0]] = val.strip("'\"")
                else:
                    pass
            elif (prev == "-v"):
                if (set(e).issubset(set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:./_"))):
                    result["-v " + e] = "1"
            elif (prev == "-n"):
                if (set(e).issubset(set("abcdefghijklmnopqrstuvwxyz0123456789-"))):
                    result["-n " + e] = "1"
            else:
                result[prev] = e
            prev = None
    return result


# ---------------------------------------------------------------------------
# List / threading helpers
# ---------------------------------------------------------------------------

def split_list(lst, k):
    """
    Splits a list into sublists of maximum size k.
    """
    return [lst[i:i + k] for i in range(0, len(lst), k)]


def exec_with_threads(f, args, nt=16, max_retries=5):
    def worker(sub_args):
        for arg in sub_args:
            retries = 0
            while retries <= max_retries:
                try:
                    result = None
                    if isinstance(arg, tuple):
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


# ---------------------------------------------------------------------------
# Date / scheduling helpers
# ---------------------------------------------------------------------------

def convert_timestamp_to_date(unix_timestamp):
    utc_datetime = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
    return utc_datetime.strftime("%Y-%m-%d")

def parse_day_cron_style(value):
    """
    Accepts an integer string 0-6 or '*' to indicate 'Every day'.
    Returns 0-6 as int, or None if '*'.
    """
    val = str(value).strip()
    if val == "*":
        return None
    try:
        day = int(val)
        if 0 <= day <= 6:
            return day
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("Day must be 0-6 (0=Sunday) or '*' for every day.")

def parse_hour_cron_style(value):
    """
    Accepts an integer string 0-23 or '*' to indicate 'Every hour'.
    Returns 0-23 as int, or None if '*'.
    """
    val = str(value).strip()
    if val == "*":
        return None
    try:
        hour = int(val)
        if 0 <= hour <= 23:
            return hour
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("Hour must be 0-23 or '*' for every hour.")

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
            print(f"Warning: Invalid start date format! Ignoring start date! \n {str(e)}")

    return start_timestamp, end_timestamp


# ---------------------------------------------------------------------------
# Georegion mapping and query/result hooks
# ---------------------------------------------------------------------------

_regions = {
    'AF': ('DZ,AO,BJ,BW,BF,BI,CM,CV,CF,TD,KM,CD,CG,DJ,EG,GQ,ER,ET,GA,GM,GH,GN,'
           'GW,KE,LS,LR,LY,MW,MA,ML,MR,MU,MZ,NA,NE,NG,RW,SH,ST,SN,SC,SL,SO,ZA,'
           'SS,SD,SZ,TZ,TG,TN,UG,YE,ZM,ZW'),  # Africa
    'AS': ('AE,AM,AR,AU,AZ,BD,BH,BN,BT,MM,KH,KP,IN,ID,IR,IQ,IL,JP,JO,KZ,LV,'
           'LI,MY,MV,MN,NP,KR,PK,PH,QA,SA,SG,LK,SY,TW,TJ,TH,TR,TM,VN,YE,HK,'
           'CN,OM'),  # Asia
    'EU': ('AL,AD,AT,BY,BE,BA,BG,HR,CY,CZ,DK,EE,'
           'FI,FR,GE,DE,GR,HU,IS,IT,KZ,LV,LI,LT,'
           'LU,MT,MD,MC,ME,NL,NO,PL,PT,RO,RU,RS,'
           'SK,SI,ES,SE,CH,UA,GB,VA,MK'),  # Europe
    'LC': ('AG,AR,BS,BB,BZ,BO,BR,CL,CO,CR,CU,DO,EC,SV,GY,HT,HN,JM,MX,NI,PA,PY,'
           'PE,PR,RD,SUR,TT,UR,VZ'),  # Latin America and the Caribbean
    'NA': 'CA,US',  # Northern America
    'OC': ('AU,FJ,GU,KI,MH,FM,NR,NZ,PG,PW,SL,TO,TV,VU'),  # Oceania
}


def _reverse_mapping(regions):
    reversed_mapping = {}
    for region, countries in regions.items():
        for country in countries.split(','):
            reversed_mapping[country] = region
    return reversed_mapping


_regions_rev = _reverse_mapping(_regions)


def preprocess_search_query(query_str):
    """Pre-process a query string to expand georegion and chunked directives.

    If the query contains ``georegion=true``, any ``geolocation = <REGION_CODE>``
    clause is expanded into ``geolocation in [<country_list>]`` using :data:`_regions`.

    Both ``georegion=true`` and ``chunked=true`` are stripped from the query
    before it reaches the API.

    Returns:
        A ``(georegion_active, chunked_active, processed_query_str)`` tuple.
    """
    if query_str is None:
        return False, False, query_str

    from pyparsing import Word, alphas, alphanums, one_of, Group, ZeroOrMore

    key = Word(alphas + "_", alphanums + "_")
    operator = one_of("= in != > < >= <=")
    value = Word(alphanums + "_")
    expr = Group(key + operator + value)
    query = ZeroOrMore(expr)
    parsed = query.parse_string(query_str)

    directives = {'georegion', 'chunked'}
    state = {}
    for d in directives:
        state[d] = any([d, '=', 'true'] == list(e) for e in parsed)

    if not any(state.values()):
        return False, False, query_str

    parts = []
    for e in parsed:
        if e[0] in directives:
            continue
        elif e[0] == 'geolocation' and state['georegion'] and e[2] in _regions:
            parts.append(f'geolocation in [{_regions[e[2]]}]')
        else:
            parts.append(' '.join(e))

    return state['georegion'], state['chunked'], ' '.join(parts)


def postprocess_search_results(results, georegion_active=False, chunked=False):
    """Post-process search results with datacenter flag, georegion, and chunked filters.

    Always adds a ``datacenter`` boolean derived from ``hosting_type``.
    When *georegion_active*, appends continent codes to geolocation.
    When *chunked*, filters and rounds values for skypilot compatibility.
    """
    _chunked_cutoffs = {
        'cpu_ram': 64 * 1024,
        'cpu_cores': 32,
        'min_bid': 0,
    }

    filtered = []
    for res in results:
        res['datacenter'] = (res.get('hosting_type') == 1)

        if georegion_active:
            geo = res.get('geolocation', '')
            if geo:
                country = geo[-2:]
                region = _regions_rev.get(country)
                if region:
                    res['geolocation'] = f'{geo}, {region}'

        if chunked:
            good = True
            try:
                for k, v in _chunked_cutoffs.items():
                    if res.get(k) is not None and res[k] < v:
                        good = False
                    else:
                        res[k] = v
            except Exception:
                good = False
            if not good:
                continue
            res['gpu_ram'] = res.get('gpu_ram', 0) & 0xffffffffff0
            res['disk_space'] = int(res.get('disk_space', 0)) & 0xffffffffffc0

        filtered.append(res)

    return filtered
