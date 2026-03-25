"""CLI commands for billing, invoices, earnings, and user account management."""

import json
import time
from copy import deepcopy
from datetime import datetime, timezone
from io import StringIO

from vastai.cli.parser import argument
from vastai.cli.display import (
    display_table, invoice_fields, user_fields, ipaddr_fields,
    scheduled_jobs_fields, deindent, print_or_page,
)
from vastai.api import billing as billing_api
from vastai.api import auth as auth_api
from vastai.api import teams as teams_api


from vastai.cli.utils import get_parser as _get_parser, get_client  # noqa: F401


parser = _get_parser()


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def convert_timestamp_to_date(unix_timestamp):
    utc_datetime = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
    return utc_datetime.strftime("%Y-%m-%d")


def to_timestamp_(val):
    """Convert a date string or int to a UNIX timestamp."""
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        if val.isdigit():
            return int(val)
        return int(datetime.strptime(val + "+0000", '%Y-%m-%d%z').timestamp())
    raise ValueError("Invalid date format")


def _sum(X, k):
    y = 0
    for x in X:
        a = float(x.get(k, 0))
        y += a
    return y


def _select(X, k):
    Y = set()
    for x in X:
        v = x.get(k, None)
        if v is not None:
            Y.add(v)
    return Y


def convert_dates_to_timestamps(args):
    """Convert start_date/end_date from args into UNIX timestamps."""
    end_timestamp = time.time()
    start_timestamp = time.time() - (24 * 60 * 60)

    import dateutil
    from dateutil import parser as dateutil_parser

    if args.end_date:
        try:
            end_date = dateutil_parser.parse(str(args.end_date))
            end_timestamp = time.mktime(end_date.timetuple())
        except ValueError as e:
            print(f"Warning: Invalid end date format! Ignoring end date! \n {str(e)}")

    if args.start_date:
        try:
            start_date = dateutil_parser.parse(str(args.start_date))
            start_timestamp = time.mktime(start_date.timetuple())
        except ValueError as e:
            print(f"Warning: Invalid start date format! Ignoring start date! \n {str(e)}")

    return start_timestamp, end_timestamp


def filter_invoice_items(args, rows):
    """Filter invoice items by date range and charge/credit type."""
    from datetime import date

    try:
        import dateutil
        from dateutil import parser as dateutil_parser
    except ImportError:
        print("\nWARNING: Missing dateutil, can't parse time format")

    end_timestamp = 9999999999
    start_timestamp = 0
    start_date_txt = ""
    end_date_txt = ""

    if args.end_date:
        try:
            end_date = dateutil_parser.parse(str(args.end_date))
            end_date_txt = end_date.isoformat()
            end_timestamp = time.mktime(end_date.timetuple())
        except ValueError:
            print("Warning: Invalid end date format! Ignoring end date!")
    if args.start_date:
        try:
            start_date = dateutil_parser.parse(str(args.start_date))
            start_date_txt = start_date.isoformat()
            start_timestamp = time.mktime(start_date.timetuple())
        except ValueError:
            print("Warning: Invalid start date format! Ignoring start date!")

    selector_flag = ""
    if args.only_charges:
        type_txt = "Only showing charges."
        selector_flag = "only_charges"
        def type_filter_fn(row):
            return row["type"] == "charge"
    elif args.only_credits:
        type_txt = "Only showing credits."
        selector_flag = "only_credits"
        def type_filter_fn(row):
            return row["type"] == "payment"
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

    rows = list(filter(
        lambda row: end_timestamp >= (row["timestamp"] or 0.0) >= start_timestamp
        and type_filter_fn(row) and float(row["amount"]) != 0,
        rows
    ))

    if start_date_txt:
        start_date_txt = "S:" + start_date_txt
    if end_date_txt:
        end_date_txt = "E:" + end_date_txt

    now = date.today()
    invoice_number = now.year * 12 + now.month - 1

    pdf_filename_fields = list(filter(
        lambda fld: fld != "",
        [str(invoice_number), start_date_txt, end_date_txt, selector_flag]
    ))
    filename = "invoice_" + "-".join(pdf_filename_fields) + ".pdf"
    return {"rows": rows, "header_text": header_text, "pdf_filename": filename}


# ---------------------------------------------------------------------------
# Invoices-v1 helpers (rich formatting)
# ---------------------------------------------------------------------------

charge_types = ['instance', 'volume', 'serverless', 'i', 'v', 's']
invoice_types = {
    "transfers": "transfer",
    "stripe": "stripe_payments",
    "bitpay": "bitpay",
    "coinbase": "coinbase",
    "crypto.com": "crypto.com",
    "reserved": "instance_prepay",
    "payout_paypal": "paypal_manual",
    "payout_wise": "wise_manual",
}


def format_invoices_charges_results(args, results):
    indices_to_remove = []
    for i, item in enumerate(results):
        item['start'] = convert_timestamp_to_date(item['start']) if item['start'] else None
        item['end'] = convert_timestamp_to_date(item['end']) if item['end'] else None
        if item['amount'] == 0:
            indices_to_remove.append(i)
        elif args.invoices:
            if item['type'] not in {'transfer', 'payout'}:
                item['amount'] *= -1
            item['amount_str'] = f"${item['amount']:.2f}" if item['amount'] > 0 else f"-${abs(item['amount']):.2f}"
        else:
            item['amount'] = f"${item['amount']:.3f}"

        if args.charges:
            if item['type'] in {'instance', 'volume'} and not args.verbose:
                item['items'] = []
            if item['source'] and '-' in item['source']:
                item['type'], item['source'] = item['source'].capitalize().split('-')

        item['items'] = format_invoices_charges_results(args, item['items'])

    for i in reversed(indices_to_remove):
        del results[i]

    return results


def rich_object_to_string(rich_obj, no_color=True):
    """Render a Rich object (Table or Tree) to a string."""
    from rich.console import Console
    buffer = StringIO()
    console = Console(record=True, file=buffer)
    console.print(rich_obj)
    return console.export_text(clear=True, styles=not no_color)


def create_charges_tree(results, parent=None, title="Charges Breakdown"):
    """Build and return a Rich Tree from nested charge results."""
    from rich.text import Text
    from rich.tree import Tree
    from rich.panel import Panel
    if parent is None:
        root = Tree(Text(title, style="bold red"))
        create_charges_tree(results, root)
        return Panel(root, style="white on #000000", expand=False)

    top_level = (parent.label.plain == title)
    for item in results:
        end_date = f" -> {item['end']}" if item['start'] != item['end'] else ""
        label = Text.assemble(
            (item["type"], "bold cyan"),
            (f" {item['source']}" if item.get('source') else "", "gold1"), " -> ",
            (f"{item['amount']}", 'bold green1' if top_level else 'green1'),
            (f" -- {item['description']}", "bright_white" if top_level else "dim white"),
            (f"  ({item['start']}{end_date})", "bold bright_white" if top_level else "white")
        )
        node = parent.add(label, guide_style="blue3")
        if item.get("items"):
            create_charges_tree(item["items"], node)
    return parent


def create_rich_table_for_charges(args, results):
    """Build and return a Rich Table from charge results."""
    from rich.table import Table
    from rich.text import Text
    from rich import box
    from rich.padding import Padding
    table = Table(style="white", header_style="bold bright_yellow", box=box.DOUBLE_EDGE, row_styles=["on grey11", "none"])
    table.add_column(Text("Type", justify="center"), style="bold steel_blue1", justify="center")
    table.add_column(Text("ID", justify="center"), style="gold1", justify="center")
    table.add_column(Text("Amount", justify="center"), style="sea_green2", justify="right")
    table.add_column(Text("Start", justify="center"), style="bright_white", justify="center")
    table.add_column(Text("End", justify="center"), style="bright_white", justify="center")
    if not args.charge_type or 'serverless' in args.charge_type:
        table.add_column(Text("Endpoint", justify="center"), style="bright_red", justify="center")
        table.add_column(Text("Workergroup", justify="center"), style="orchid", justify="center")
    for item in results:
        row = [item['type'].capitalize(), item['source'], item['amount'], item['start'], item['end']]
        if not args.charge_type or 'serverless' in args.charge_type:
            row.append(str(item['metadata'].get('endpoint_id', '')))
            row.append(str(item['metadata'].get('workergroup_id', '')))
        table.add_row(*row)
    return Padding(table, (1, 2), style="on #000000", expand=False)


def create_rich_table_for_invoices(results):
    """Build and return a Rich Table from invoice results."""
    from rich.table import Table
    from rich.text import Text
    from rich import box
    from rich.padding import Padding
    invoice_type_to_color = {
        "credit": "green1",
        "transfer": "gold1",
        "payout": "orchid",
        "reserved": "sky_blue1",
        "refund": "bright_red",
    }
    table = Table(style="white", header_style="bold bright_yellow", box=box.DOUBLE_EDGE, row_styles=["on grey11", "none"])
    table.add_column(Text("ID", justify="center"), style="bright_white", justify="center")
    table.add_column(Text("Created", justify="center"), style="yellow3", justify="center")
    table.add_column(Text("Paid", justify="center"), style="yellow3", justify="center")
    table.add_column(Text("Type", justify="center"), justify="center")
    table.add_column(Text("Result", justify="center"), justify="right")
    table.add_column(Text("Source", justify="center"), style="bright_cyan", justify="center")
    table.add_column(Text("Description", justify="center"), style="bright_white", justify="left")
    for item in results:
        table.add_row(
            str(item['metadata']['invoice_id']),
            item['start'],
            item['end'] if item['end'] else 'N/A',
            Text(item['type'].capitalize(), style=invoice_type_to_color.get(item['type'], "white")),
            Text(item['amount_str'], style="sea_green2" if item['amount'] > 0 else "bright_red"),
            item['source'].capitalize() if item['type'] != 'transfer' else item['source'],
            item['description'],
        )
    return Padding(table, (1, 2), style="on #000000", expand=False)


# ---------------------------------------------------------------------------
# show invoices (deprecated)
# ---------------------------------------------------------------------------

@parser.command(
    argument("-q", "--quiet", action="store_true", help="only display numeric ids"),
    argument("-s", "--start_date", help="start date and time for report. Many formats accepted", type=str),
    argument("-e", "--end_date", help="end date and time for report. Many formats accepted", type=str),
    argument("-c", "--only_charges", action="store_true", help="Show only charge items"),
    argument("-p", "--only_credits", action="store_true", help="Show only credit items"),
    argument("--instance_label", help="Filter charges on a particular instance label (useful for autoscaler groups)"),
    usage="(DEPRECATED) vastai show invoices [OPTIONS]",
    help="(DEPRECATED) Get billing history reports",
)
def show__invoices(args):
    """Show current payments and charges (deprecated)."""
    client = get_client(args)

    sdate, edate = convert_dates_to_timestamps(args)
    result = billing_api.show_invoices(client, start_date=args.start_date, end_date=args.end_date,
                                       only_charges=args.only_charges, only_credits=args.only_credits)
    rows = result["invoices"]
    current_charges = result["current"]

    invoice_filter_data = filter_invoice_items(args, rows)
    rows = invoice_filter_data["rows"]
    filter_header = invoice_filter_data["header_text"]

    contract_ids = None
    if args.instance_label:
        contract_ids = _select(rows, 'instance_id')
        req_json = {
            "label": args.instance_label,
            "contract_ids": list(contract_ids)
        }
        if args.explain:
            print("request json: ")
            print(req_json)
        result2 = client.post("/contracts/fetch/", json_data=req_json)
        result2.raise_for_status()
        filtered_rows = result2.json()["contracts"]
        contract_ids = _select(filtered_rows, 'id')
        rows2 = []
        for row in rows:
            id = row.get("instance_id", None)
            if id in contract_ids:
                rows2.append(row)
        rows = rows2

    if args.quiet:
        for row in rows:
            id = row.get("id", None)
            if id is not None:
                print(id)
    elif args.raw:
        return rows
    else:
        print(filter_header)
        display_table(rows, invoice_fields)
        print(f"Total: ${_sum(rows, 'amount')}")
        print("Current: ", current_charges)


# ---------------------------------------------------------------------------
# show invoices-v1 (advanced with pagination and rich formatting)
# ---------------------------------------------------------------------------

@parser.command(
    argument('-i', '--invoices', mutex_group='grp', action='store_true', required=True, help='Show invoices instead of charges'),
    argument('-it', '--invoice-type', choices=invoice_types.keys(), nargs='+', metavar='type',
             help=f'Filter which types of invoices to show: {{{", ".join(invoice_types.keys())}}}'),
    argument('-c', '--charges', mutex_group='grp', action='store_true', required=True, help='Show charges instead of invoices'),
    argument('-ct', '--charge-type', choices=charge_types, nargs='+', metavar='type',
             help='Filter which types of charges to show: {i|instance, v|volume, s|serverless}'),
    argument('-s', '--start-date', help='Start date (YYYY-MM-DD or timestamp)'),
    argument('-e', '--end-date', help='End date (YYYY-MM-DD or timestamp)'),
    argument('-l', '--limit', type=int, default=20, help='Number of results per page (default: 20, max: 100)'),
    argument('-t', '--next-token', help='Pagination token for next page'),
    argument('-f', '--format', choices=['table', 'tree'], default='table', help='Output format for charges (default: table)'),
    argument('-v', '--verbose', action='store_true', help='Include full Instance Charge details and Invoice Metadata (tree view only)'),
    argument('--latest-first', action='store_true', help='Sort by latest first'),
    usage="vastai show invoices-v1 [OPTIONS]",
    help="Get billing (invoices/charges) history reports with advanced filtering and pagination",
    epilog=deindent("""
        This command supports colored output and rich formatting if the 'rich' python module is installed!

        Examples:
            # Show the first 20 invoices in the last week
            vastai show invoices-v1 --invoices

            # Show the first 50 charges over a 7 day period starting from 2025-11-30 in tree format
            vastai show invoices-v1 --charges -s 2025-11-30 -f tree -l 50

            # Show the first 20 invoices of specific types for the month of November 2025
            vastai show invoices-v1 -i -it stripe bitpay transfers --start-date 2025-11-01 --end-date 2025-11-30

            # Show the first 20 charges for only volumes and serverless instances between two dates
            vastai show invoices-v1 -c --charge-type v s -s 2025-11-01 -e 2025-11-05 --format tree --verbose

            # Get the next page of paginated invoices
            vastai show invoices-v1 --invoices --limit 50 --next-token <TOKEN>

            # Show the last 10 instance charges sorted by latest first
            vastai show invoices-v1 --charges -ct instance --end-date 2025-12-25 -l 10 --latest-first
    """),
)
def show__invoices_v1(args):
    """Get billing (invoices/charges) history with advanced filtering and pagination."""
    output_lines = []
    try:
        from rich.prompt import Confirm
        has_rich = True
    except ImportError:
        output_lines.append("NOTE: To view results in color and table/tree format please install the 'rich' python module with 'pip install rich'\n")
        has_rich = False

    # Handle default start and end date values
    if not args.start_date and not args.end_date:
        args.end_date = int(time.time())
    if not args.start_date:
        args.start_date = args.end_date - 7 * 24 * 60 * 60
    elif not args.end_date:
        args.end_date = args.start_date + 7 * 24 * 60 * 60

    try:
        start_timestamp = to_timestamp_(args.start_date)
        end_timestamp = to_timestamp_(args.end_date)
    except Exception as e:
        print(f"Error parsing dates: {e}")
        print("Use format YYYY-MM-DD or UNIX timestamp")
        return

    if has_rich and not args.no_color:
        print("(use --no-color to disable colored output)\n")

    start_date = convert_timestamp_to_date(start_timestamp)
    end_date = convert_timestamp_to_date(end_timestamp)
    data_type = "Instance Charges" if args.charges else "Invoices"
    output_lines.append(f"Fetching {data_type} from {start_date} to {end_date}...")

    # Build SDK params
    params = {
        "charges": args.charges,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "limit": min(args.limit, 100) if args.limit > 0 else 20,
        "latest_first": args.latest_first,
        "format": args.format if args.charges else "table",
        "charge_type": args.charge_type or [],
        "invoice_type": args.invoice_type or [],
        "next_token": args.next_token,
    }

    client = get_client(args)
    found_results, found_count = [], 0
    looping = True
    while looping:
        response = billing_api.show_invoices_v1(client, params)

        found_results += response.get('results', [])
        found_count += response.get('count', 0)
        total = response.get('total', 0)
        next_token = response.get('next_token')

        if args.raw or has_rich is False:
            output_lines.append("Raw response:\n" + json.dumps(response, indent=2))
            if next_token:
                print(f"Next page token: {next_token}\n")
        elif not found_results:
            output_lines.append("No results found")
        else:
            formatted_results = format_invoices_charges_results(args, deepcopy(found_results))
            if args.invoices:
                rich_obj = create_rich_table_for_invoices(formatted_results)
            elif args.format == 'tree':
                rich_obj = create_charges_tree(formatted_results)
            else:
                rich_obj = create_rich_table_for_charges(args, formatted_results)

            output_lines.append(rich_object_to_string(rich_obj, no_color=args.no_color))
            output_lines.append(f"Showing {found_count} of {total} results")
            if next_token:
                output_lines.append(f"Next page token: {next_token}\n")

        paging = print_or_page(args, '\n'.join(output_lines))

        if next_token and not paging:
            if has_rich:
                ans = Confirm.ask("Fetch next page?", show_default=False, default=False)
            else:
                ans = input("Fetch next page? (y/N): ").strip().lower() == 'y'
            if ans:
                params['next_token'] = next_token
                output_lines.clear()
                args.full = True
            else:
                looping = False
        else:
            looping = False


# ---------------------------------------------------------------------------
# show earnings
# ---------------------------------------------------------------------------

@parser.command(
    argument("-q", "--quiet", action="store_true", help="only display numeric ids"),
    argument("-s", "--start_date", help="start date and time for report. Many formats accepted", type=str),
    argument("-e", "--end_date", help="end date and time for report. Many formats accepted", type=str),
    argument("-m", "--machine_id", help="Machine id (optional)", type=int),
    usage="vastai show earnings [OPTIONS]",
    help="Get machine earning history reports",
)
def show__earnings(args):
    """Show earnings history for a time range, optionally per machine."""
    client = get_client(args)
    rows = billing_api.show_earnings(client, start_date=args.start_date, end_date=args.end_date,
                                     machine_id=args.machine_id)

    if args.raw:
        return rows
    print(json.dumps(rows, indent=1, sort_keys=True))


# ---------------------------------------------------------------------------
# show deposit
# ---------------------------------------------------------------------------

@parser.command(
    argument("id", help="id of instance to get info for", type=int),
    usage="vastai show deposit ID [options]",
    help="Display reserve deposit info for an instance",
)
def show__deposit(args):
    """Show reserve deposit info for an instance."""
    client = get_client(args)
    result = billing_api.show_deposit(client, id=args.id)
    print(json.dumps(result, indent=1, sort_keys=True))


# ---------------------------------------------------------------------------
# show / set user
# ---------------------------------------------------------------------------

@parser.command(
    argument("-q", "--quiet", action="store_true", help="display information about user"),
    usage="vastai show user [OPTIONS]",
    help="Get current user data",
    epilog=deindent("""
        Shows stats for logged-in user. These include user balance, email, and ssh key. Does not show API key.
    """),
)
def show__user(args):
    """Show stats for logged-in user."""
    client = get_client(args)
    user_blob = billing_api.show_user(client)

    if args.raw:
        return user_blob
    else:
        display_table([user_blob], user_fields)


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
    """),
)
def set__user(args):
    """Update user data from a json file."""
    params = None
    with open(args.file, 'r') as file:
        params = json.load(file)
    client = get_client(args)
    result = billing_api.set_user(client, params=params)
    print(f"{result}")


# ---------------------------------------------------------------------------
# show subaccounts / create subaccount
# ---------------------------------------------------------------------------

@parser.command(
    argument("-q", "--quiet", action="store_true", help="display subaccounts from current user"),
    usage="vastai show subaccounts [OPTIONS]",
    help="Get current subaccounts",
)
def show__subaccounts(args):
    """Show subaccounts."""
    client = get_client(args)
    rows = billing_api.show_subaccounts(client)
    if args.raw:
        return rows
    else:
        display_table(rows, user_fields)


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
    """Create a subaccount under your current account."""
    host_only = False
    if args.type:
        host_only = args.type.lower() == "host"

    if getattr(args, 'explain', False):
        print("Request JSON would be: ")
        print({
            "email": args.email, "username": args.username,
            "password": args.password, "host_only": host_only, "parent_id": "me",
        })
        return

    client = get_client(args)
    try:
        rj = billing_api.create_subaccount(client, email=args.email, username=args.username,
                                           password=args.password, host_only=host_only)
        print(rj)
    except Exception as e:
        print(f"Failed with error: {e}")


# ---------------------------------------------------------------------------
# show ipaddrs
# ---------------------------------------------------------------------------

@parser.command(
    usage="vastai show ipaddrs [--api-key API_KEY] [--raw]",
    help="Display user's history of ip addresses",
)
def show__ipaddrs(args):
    """Show the history of ip address accesses."""
    client = get_client(args)
    rows = billing_api.show_ipaddrs(client)
    if args.raw:
        return rows
    else:
        display_table(rows, ipaddr_fields)


# ---------------------------------------------------------------------------
# transfer credit
# ---------------------------------------------------------------------------

@parser.command(
    argument("recipient", help="email (or id) of recipient account", type=str),
    argument("amount", help="$dollars of credit to transfer", type=float),
    argument("--skip", help="skip confirmation", action="store_true", default=False),
    usage="vastai transfer credit RECIPIENT AMOUNT",
    help="Transfer credits to another account",
)
def transfer__credit(args):
    """Transfer credits to another account."""
    if not args.skip:
        print(f"Transfer ${args.amount} credit to account {args.recipient}?  This is irreversible.")
        ok = input("Continue? [y/n] ")
        if ok.strip().lower() != "y":
            return

    if args.explain:
        print("request json: ")
        print({"sender": "me", "recipient": args.recipient, "amount": args.amount})

    client = get_client(args)
    try:
        rj = teams_api.transfer_credit(client, recipient=args.recipient, amount=args.amount)
        if rj["success"]:
            print(f"Sent {args.amount} to {args.recipient}")
        else:
            print(rj["msg"])
    except Exception as e:
        print(f"Failed with error: {e}")


# ---------------------------------------------------------------------------
# scheduled jobs
# ---------------------------------------------------------------------------

def normalize_schedule_fields(job):
    """Mutates the job dict to replace None values with readable scheduling labels."""
    if job.get("day_of_the_week") is None:
        job["day_of_the_week"] = "Everyday"
    else:
        days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        job["day_of_the_week"] = days[int(job["day_of_the_week"])]

    if job.get("hour_of_the_day") is None:
        job["hour_of_the_day"] = "Every hour"
    else:
        hour = int(job["hour_of_the_day"])
        suffix = "AM" if hour < 12 else "PM"
        hour_12 = hour % 12
        hour_12 = 12 if hour_12 == 0 else hour_12
        job["hour_of_the_day"] = f"{hour_12}_{suffix}"

    if job.get("min_of_the_hour") is None:
        job["min_of_the_hour"] = "Every minute"
    else:
        job["min_of_the_hour"] = f"{int(job['min_of_the_hour']):02d}"

    return job


@parser.command(
    usage="vastai show scheduled-jobs [--api-key API_KEY] [--raw]",
    help="Display the list of scheduled jobs",
)
def show__scheduled_jobs(args):
    """Show the list of scheduled jobs for the account."""
    client = get_client(args)
    rows = auth_api.show_scheduled_jobs(client)
    if args.raw:
        return rows
    else:
        rows = [normalize_schedule_fields(job) for job in rows]
        display_table(rows, scheduled_jobs_fields)


@parser.command(
    argument("id", help="id of scheduled job to remove", type=int),
    usage="vastai delete scheduled-job ID",
    help="Delete a scheduled job",
)
def delete__scheduled_job(args):
    """Delete a scheduled job."""
    client = get_client(args)
    result = auth_api.delete_scheduled_job(client, id=args.id)
    print(result)
