"""CLI commands for searching offers, templates, and benchmarks."""

import json
import time

from vastai.cli.parser import argument, hidden_aliases
from vastai.cli.display import display_table, displayable_fields, displayable_fields_reserved, deindent
from vastai.api import offers as offers_api


from vastai.cli.utils import get_parser as _get_parser, get_client  # noqa: F401


parser = _get_parser()


# ---------------------------------------------------------------------------
# search offers
# ---------------------------------------------------------------------------

@parser.command(
    argument("-t", "--type", default="on-demand", help="Show 'on-demand', 'reserved', or 'bid'(interruptible) pricing. default: on-demand"),
    argument("-i", "--interruptible", dest="type", const="bid", action="store_const", help="Alias for --type=bid"),
    argument("-b", "--bid", dest="type", const="bid", action="store_const", help="Alias for --type=bid"),
    argument("-r", "--reserved", dest="type", const="reserved", action="store_const", help="Alias for --type=reserved"),
    argument("-d", "--on-demand", dest="type", const="on-demand", action="store_const", help="Alias for --type=on-demand"),
    argument("-n", "--no-default", action="store_true", help="Disable default query"),
    argument("--new", action="store_true", help="New search exp"),
    argument("--limit", type=int, help=""),
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
    from vastai.api.query import parse_query, offers_fields, offers_alias, offers_mult

    try:
        if args.no_default:
            query = {}
        else:
            query = {"verified": {"eq": True}, "external": {"eq": False}, "rentable": {"eq": True}, "rented": {"eq": False}}

        if args.query is not None:
            query = parse_query(args.query, query, offers_fields, offers_alias, offers_mult)

        order = []
        for name in args.order.split(","):
            name = name.strip()
            if not name:
                continue
            direction = "asc"
            field = name
            if name.strip("-") != name:
                direction = "desc"
                field = name.strip("-")
            if name.strip("+") != name:
                direction = "asc"
                field = name.strip("+")
            if field in offers_alias:
                field = offers_alias[field]
            order.append([field, direction])

        query["order"] = order
        query["type"] = args.type
        if args.limit:
            query["limit"] = int(args.limit)
        query["allocated_storage"] = args.storage
        if query["type"] == 'interruptible':
            query["type"] = 'bid'
    except ValueError as e:
        print("Error: ", e)
        return 1

    json_blob = query
    client = get_client(args)

    if args.new:
        json_blob = {"select_cols": ['*'], "q": query}
        if args.explain:
            print("request json: ")
            print(json_blob)
        r = client.put("/search/asks/", json_data=json_blob)
    else:
        if args.explain:
            print("request json: ")
            print(json_blob)
        r = client.post("/bundles/", json_data=json_blob)

    r.raise_for_status()

    if r.headers.get('Content-Type') != 'application/json':
        print(f"invalid return Content-Type: {r.headers.get('Content-Type')}")
        return

    rows = r.json()["offers"]

    if 'rented' in query:
        filter_q = query['rented']
        filter_op = list(filter_q.keys())[0]
        target = filter_q[filter_op]
        new_rows = []
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


# ---------------------------------------------------------------------------
# search benchmarks
# ---------------------------------------------------------------------------

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
    from vastai.api.query import parse_query, benchmarks_fields, fix_date_fields

    try:
        query = {}
        if args.query is not None:
            query = parse_query(args.query, query, benchmarks_fields)
            query = fix_date_fields(query, ['last_update'])
    except ValueError as e:
        print("Error: ", e)
        return 1

    client = get_client(args)
    rows = offers_api.search_benchmarks(client, query=query)
    if True:
        return rows
    else:
        display_table(rows, displayable_fields)


# ---------------------------------------------------------------------------
# search templates
# ---------------------------------------------------------------------------

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
    from vastai.api.query import parse_query, templates_fields, fix_date_fields

    try:
        query = {}
        if args.query is not None:
            query = parse_query(args.query, query, templates_fields)
            query = fix_date_fields(query, ['created_at', 'recent_create_date'])
    except ValueError as e:
        print("Error: ", e)
        return 1

    client = get_client(args)
    try:
        rows = offers_api.search_templates(client, query=query)
        print(json.dumps(rows, indent=1, sort_keys=True))
    except Exception as e:
        print(f"Error: {e}")


# ---------------------------------------------------------------------------
# search invoices
# ---------------------------------------------------------------------------

@parser.command(
    argument("query", help="Search query in simple query syntax (see below)", nargs="*", default=None),
    usage="vastai search invoices [--help] [--api-key API_KEY] [--raw] <query>",
    help="Search for invoices using custom query",
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
    """Search for invoices using custom query."""
    from vastai.api.query import parse_query, invoices_fields, fix_date_fields

    try:
        query = {}
        if args.query is not None:
            query = parse_query(args.query, query, invoices_fields)
            query = fix_date_fields(query, ['when', 'paid_on', 'payment_expected'])
    except ValueError as e:
        print("Error: ", e)
        return 1

    client = get_client(args)
    rows = offers_api.search_invoices(client, query=query)
    if True:
        return rows
    else:
        print(json.dumps(rows, indent=1, sort_keys=True))


# ---------------------------------------------------------------------------
# create / update / delete template
# ---------------------------------------------------------------------------

@parser.command(
    argument("--name", help="name of the template", type=str),
    argument("--image", help="docker container image to launch", type=str),
    argument("--image_tag", help="docker image tag", type=str),
    argument("--href", help="link you want to provide", type=str),
    argument("--repo", help="link to repository", type=str),
    argument("--login", help="docker login arguments for private repo authentication, surround with ''", type=str),
    argument("--env", help="Contents of the 'Docker options' field", type=str),
    argument("--ssh", help="Launch as an ssh instance type", action="store_true"),
    argument("--jupyter", help="Launch as a jupyter instance instead of an ssh instance", action="store_true"),
    argument("--direct", help="Use (faster) direct connections for jupyter & ssh", action="store_true"),
    argument("--jupyter-dir", help="For runtype 'jupyter', directory in instance to use to launch jupyter", type=str),
    argument("--jupyter-lab", help="For runtype 'jupyter', Launch instance with jupyter lab", action="store_true"),
    argument("--onstart-cmd", help="contents of onstart script as single argument", type=str),
    argument("--search_params", help="search offers filters", type=str),
    argument("-n", "--no-default", action="store_true", help="Disable default search param query args"),
    argument("--disk_space", help="disk storage space, in GB", type=str),
    argument("--readme", help="readme string", type=str),
    argument("--hide-readme", help="hide the readme from users", action="store_true"),
    argument("--desc", help="description string", type=str),
    argument("--public", help="make template available to public", action="store_true"),
    usage="vastai create template",
    help="Create a new template",
)
def create__template(args):
    """Create a new template."""
    from vastai.api.query import parse_query, offers_fields, offers_alias, offers_mult

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

    if args.explain:
        print("request json: ")
        print({"name": args.name, "image": args.image, "extra_filters": extra_filters})

    client = get_client(args)
    try:
        rj = offers_api.create_template(
            client, name=args.name, image=args.image, image_tag=args.image_tag,
            href=args.href, repo=args.repo, env=args.env, onstart_cmd=args.onstart_cmd,
            jup_direct=jup_direct, ssh_direct=ssh_direct,
            use_jupyter_lab=args.jupyter_lab, runtype=runtype, use_ssh=use_ssh,
            jupyter_dir=args.jupyter_dir, docker_login_repo=docker_login_repo,
            extra_filters=extra_filters, disk_space=args.disk_space,
            readme=args.readme, readme_visible=not args.hide_readme,
            desc=args.desc, private=not args.public,
        )
        if rj.get("success"):
            print(f"New Template: {rj['template']}")
        else:
            print(rj.get('msg', rj))
    except Exception:
        print("The response is not valid JSON.")


@parser.command(
    argument("HASH_ID", help="hash id of the template", type=str),
    argument("--name", help="name of the template", type=str),
    argument("--image", help="docker container image to launch", type=str),
    argument("--image_tag", help="docker image tag", type=str),
    argument("--href", help="link you want to provide", type=str),
    argument("--repo", help="link to repository", type=str),
    argument("--login", help="docker login arguments for private repo authentication, surround with ''", type=str),
    argument("--env", help="Contents of the 'Docker options' field", type=str),
    argument("--ssh", help="Launch as an ssh instance type", action="store_true"),
    argument("--jupyter", help="Launch as a jupyter instance instead of an ssh instance", action="store_true"),
    argument("--direct", help="Use (faster) direct connections for jupyter & ssh", action="store_true"),
    argument("--jupyter-dir", help="For runtype 'jupyter', directory in instance to use to launch jupyter", type=str),
    argument("--jupyter-lab", help="For runtype 'jupyter', Launch instance with jupyter lab", action="store_true"),
    argument("--onstart-cmd", help="contents of onstart script as single argument", type=str),
    argument("--search_params", help="search offers filters", type=str),
    argument("-n", "--no-default", action="store_true", help="Disable default search param query args"),
    argument("--disk_space", help="disk storage space, in GB", type=str),
    argument("--readme", help="readme string", type=str),
    argument("--hide-readme", help="hide the readme from users", action="store_true"),
    argument("--desc", help="description string", type=str),
    argument("--public", help="make template available to public", action="store_true"),
    usage="vastai update template HASH_ID",
    help="Update an existing template",
)
def update__template(args):
    """Update an existing template."""
    from vastai.api.query import parse_query, offers_fields, offers_alias, offers_mult

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

    if args.explain:
        print("request json: ")
        print({"hash_id": args.HASH_ID, "name": args.name, "image": args.image})

    client = get_client(args)
    try:
        rj = offers_api.update_template(
            client, hash_id=args.HASH_ID, name=args.name, image=args.image,
            image_tag=args.image_tag, href=args.href, repo=args.repo, env=args.env,
            onstart_cmd=args.onstart_cmd, jup_direct=jup_direct, ssh_direct=ssh_direct,
            use_jupyter_lab=args.jupyter_lab, runtype=runtype, use_ssh=use_ssh,
            jupyter_dir=args.jupyter_dir, docker_login_repo=docker_login_repo,
            extra_filters=extra_filters, disk_space=args.disk_space,
            readme=args.readme, readme_visible=not args.hide_readme,
            desc=args.desc, private=not args.public,
        )
        if rj.get("success"):
            print(f"updated template: {json.dumps(rj['template'], indent=1)}")
        else:
            print("template update failed")
    except Exception as e:
        print(str(e))


@parser.command(
    argument("--template-id", help="Template ID of Template to Delete", type=int),
    argument("--hash-id", help="Hash ID of Template to Delete", type=str),
    usage="vastai delete template [--template-id <id> | --hash-id <hash_id>]",
    help="Delete a Template",
)
def delete__template(args):
    """Delete a template."""
    if not args.hash_id and not args.template_id:
        print('ERROR: Must Specify either Template ID or Hash ID to delete a template')
        return

    if args.explain:
        print("request json: ")
        print({"hash_id": args.hash_id, "template_id": args.template_id})

    client = get_client(args)
    try:
        rj = offers_api.delete_template(client, hash_id=args.hash_id, template_id=args.template_id)
        print(rj.get('msg', rj))
    except Exception as e:
        print(f"Error: {e}")
