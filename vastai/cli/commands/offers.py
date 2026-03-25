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

        Examples:

            vastai search offers 'reliability > 0.98 num_gpus=1 gpu_name=RTX_3090 rented=False'
            vastai search offers 'compute_cap > 610 total_flops > 5 datacenter=True'
    """),
    aliases=hidden_aliases(["search instances"]),
)
def search__offers(args):
    """Search for instance types using custom query."""
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
    aliases=hidden_aliases(["search benchmarks"]),
)
def search__benchmarks(args):
    """Search for benchmark results using custom query."""
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
    aliases=hidden_aliases(["search templates"]),
)
def search__templates(args):
    """Search for templates using custom query."""
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
