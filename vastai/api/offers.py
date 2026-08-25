"""Search offers, templates, benchmarks, volumes, network volumes, and invoices."""
from vastai.api.client import VastClient
from vastai.api.instances import resolve_runtype
from vastai.api.query import (parse_order, parse_query, offers_alias,
                              offers_fields, offers_mult)
from vastai.utils import parse_env


def search_offers(client: VastClient, query: dict = None, offer_type: str = "on-demand",
                  order: list = None, limit: int = None, storage: float = 5.0,
                  no_default: bool = False, disable_bundling: bool = False) -> list:
    """Search for instance offers using a query dict.

    Args:
        client: VastClient instance.
        query: Pre-parsed query dict of filters (e.g. {"gpu_name": {"eq": "RTX 3090"}}).
        offer_type: One of "on-demand", "reserved", or "bid".
        order: List of [field, direction] pairs, e.g. [["score", "desc"]].
        limit: Max number of results.
        storage: Allocated storage in GiB for pricing (default 5.0).
        no_default: If True, skip default filters.
        disable_bundling: Deprecated bundling flag.

    Returns:
        List of offer dicts.
    """
    if no_default:
        q = query or {}
    else:
        q = {"verified": {"eq": True}, "external": {"eq": False},
             "rentable": {"eq": True}, "rented": {"eq": False}}
        if query:
            q.update(query)

    if order is not None:
        q["order"] = order
    else:
        q["order"] = [["score", "desc"]]

    q["type"] = offer_type
    if offer_type == "interruptible":
        q["type"] = "bid"

    if limit:
        q["limit"] = int(limit)
    q["allocated_storage"] = storage

    if disable_bundling:
        q["disable_bundling"] = True

    r = client.post("/bundles/", json_data=q)
    r.raise_for_status()
    return r.json()["offers"]


def search_offers_new(client: VastClient, query: dict = None, offer_type: str = "on-demand",
                      order: list = None, limit: int = None, storage: float = 5.0,
                      no_default: bool = False, disable_bundling: bool = False) -> list:
    """Search for instance offers using the new /search/asks/ endpoint.

    Args:
        client: VastClient instance.
        query: Pre-parsed query dict of filters (e.g. {"gpu_name": {"eq": "RTX 3090"}}).
        offer_type: One of "on-demand", "reserved", or "bid".
        order: List of [field, direction] pairs, e.g. [["score", "desc"]].
        limit: Max number of results.
        storage: Allocated storage in GiB for pricing (default 5.0).
        no_default: If True, skip default filters.
        disable_bundling: Deprecated bundling flag.

    Returns:
        List of offer dicts.
    """
    if no_default:
        q = query or {}
    else:
        q = {"verified": {"eq": True}, "external": {"eq": False},
             "rentable": {"eq": True}, "rented": {"eq": False}}
        if query:
            q.update(query)

    if order is not None:
        q["order"] = order
    else:
        q["order"] = [["score", "desc"]]

    q["type"] = offer_type
    if offer_type == "interruptible":
        q["type"] = "bid"

    if limit:
        q["limit"] = int(limit)
    q["allocated_storage"] = storage

    if disable_bundling:
        q["disable_bundling"] = True

    json_blob = {"select_cols": ["*"], "q": q}
    r = client.put("/search/asks/", json_data=json_blob)
    r.raise_for_status()
    return r.json()["offers"]


def search_templates(client: VastClient, query: dict = None) -> list:
    """Search for templates using a query dict.

    Args:
        client: VastClient instance.
        query: Pre-parsed query dict of select_filters.

    Returns:
        List of template dicts.
    """
    query_args = {"select_cols": ["*"], "select_filters": query or {}}
    r = client.get("/template/", query_args=query_args)
    r.raise_for_status()
    return r.json().get("templates", [])


def benchmarks_query_args(query: dict = None, order: list = None,
                          limit: int = None, after_token: str = None) -> dict:
    """Build the query args for a ``/benchmarks`` request."""
    query_args = {"select_cols": ["*"], "select_filters": query or {}}
    if order is not None:
        query_args["order_by"] = order
    if limit is not None:
        query_args["limit"] = int(limit)
    if after_token:
        query_args["after_token"] = after_token
    return query_args


def search_benchmarks(client: VastClient, query: dict = None, order: list = None,
                      limit: int = None, after_token: str = None) -> list:
    """Search for benchmarks using a query dict, as a flat list.

    Pages through ``/benchmarks``, following ``next_token`` until it is
    exhausted, and concatenates every page. The backend caps a page at 200 rows
    by default, so callers that want one page at a time should use
    :func:`search_benchmarks_v1` instead.

    Args:
        client: VastClient instance.
        query: Pre-parsed query dict of select_filters.
        order: List of {"col": ..., "dir": ...} dicts, e.g. [{"col": "last_update", "dir": "desc"}].
        limit: Max number of results per page.
        after_token: Pagination token to resume from.

    Returns:
        List of benchmark dicts.
    """
    rows = []
    params = benchmarks_query_args(query=query, order=order, limit=limit,
                                   after_token=after_token)
    while True:
        data = search_benchmarks_v1(client, params)
        rows.extend(data.get("benchmarks") or [])
        next_token = data.get("next_token")
        if not next_token:
            return rows
        params["after_token"] = next_token


def search_benchmarks_v1(client: VastClient, params: dict) -> dict:
    """Fetch one page of benchmarks using the paginated API.

    Args:
        client: VastClient instance.
        params: Dict with select_cols, select_filters, order_by, limit, after_token.

    Returns:
        Full response dict (benchmarks, benchmarks_found, next_token).
    """
    r = client.get("/benchmarks", query_args=params)
    r.raise_for_status()
    return r.json()


def search_volumes(client: VastClient, query: dict = None, order: list = None,
                   limit: int = None, storage: float = 1.0,
                   no_default: bool = False) -> list:
    """Search for volume offers.

    Args:
        client: VastClient instance.
        query: Pre-parsed query dict of filters.
        order: List of [field, direction] pairs.
        limit: Max number of results.
        storage: Allocated storage in GiB for pricing (default 1.0).
        no_default: If True, skip default filters.

    Returns:
        List of volume offer dicts.
    """
    if no_default:
        q = query or {}
    else:
        q = {"verified": {"eq": True}, "external": {"eq": False}, "disk_space": {"gte": 1}}
        if query:
            q.update(query)

    if order is not None:
        q["order"] = order
    else:
        q["order"] = [["score", "desc"]]

    if limit:
        q["limit"] = int(limit)
    q["allocated_storage"] = storage

    r = client.post("/volumes/search/", json_data=q)
    r.raise_for_status()
    return r.json()["offers"]


def search_network_volumes(client: VastClient, query: dict = None, order: list = None,
                           limit: int = None, storage: float = 1.0,
                           no_default: bool = False) -> list:
    """Search for network volume offers.

    Args:
        client: VastClient instance.
        query: Pre-parsed query dict of filters.
        order: List of [field, direction] pairs.
        limit: Max number of results.
        storage: Allocated storage in GiB for pricing (default 1.0).
        no_default: If True, skip default filters.

    Returns:
        List of network volume offer dicts.
    """
    if no_default:
        q = query or {}
    else:
        q = {"verified": {"eq": True}, "external": {"eq": False}, "disk_space": {"gte": 1}}
        if query:
            q.update(query)

    if order is not None:
        q["order"] = order
    else:
        q["order"] = [["score", "desc"]]

    if limit:
        q["limit"] = int(limit)
    q["allocated_storage"] = storage

    r = client.post("/network_volumes/search/", json_data=q)
    r.raise_for_status()
    return r.json()["offers"]


def search_invoices(client: VastClient, query: dict = None) -> list:
    """Search for invoices using a query dict.

    Args:
        client: VastClient instance.
        query: Pre-parsed query dict of select_filters.

    Returns:
        List of invoice dicts.
    """
    query_args = {"select_cols": ["*"], "select_filters": query or {}}
    r = client.get("/invoices", query_args=query_args)
    r.raise_for_status()
    return r.json()


def template_fields_from_flags(*, ssh=False, jupyter=False, direct=False,
                               jupyter_lab=False, login=None, hide_readme=False,
                               public=False, search_params=None,
                               no_default=False, always_default=False) -> dict:
    """Translate the friendly template flags into api-layer template fields.

    Shared by the CLI commands and the SDK so both publish the same surface.

    ``always_default`` seeds the default offer filters even when no
    ``search_params`` were given, which is what the CLI has always done. The SDK
    passes False: it used to send no filters at all on a template created
    without search params, and quietly starting to attach three would change
    templates that existing scripts create.
    """
    default_search_query = {}
    if not no_default and (always_default or search_params is not None):
        default_search_query = {"verified": {"eq": True}, "external": {"eq": False},
                                "rentable": {"eq": True}}

    return {
        "jup_direct": jupyter and direct,
        "ssh_direct": ssh and direct,
        "use_ssh": ssh or jupyter,
        "use_jupyter_lab": jupyter_lab,
        "runtype": "jupyter" if jupyter else ("ssh" if ssh else "args"),
        "docker_login_repo": login.split(" ")[0] if login else None,
        "extra_filters": parse_query(search_params, default_search_query,
                                     offers_fields, offers_alias, offers_mult),
        "readme_visible": not hide_readme,
        "private": not public,
    }


def create_template(client: VastClient, name: str = None, image: str = None,
                    image_tag: str = None, href: str = None, repo: str = None,
                    env: str = None, onstart_cmd: str = None,
                    jup_direct: bool = False, ssh_direct: bool = False,
                    use_jupyter_lab: bool = False, runtype: str = "args",
                    use_ssh: bool = False, jupyter_dir: str = None,
                    docker_login_repo: str = None, extra_filters: dict = None,
                    disk_space: float = None, readme: str = None,
                    readme_visible: bool = True, desc: str = None,
                    private: bool = True) -> dict:
    """Create a new template.

    Args:
        client: VastClient instance.
        name: Template name.
        image: Docker image.
        image_tag: Docker image tag.
        href: Link to provide.
        repo: Link to repository.
        env: Docker options env string.
        onstart_cmd: Onstart script contents.
        jup_direct: Supports jupyter direct.
        ssh_direct: Supports ssh direct.
        use_jupyter_lab: Launch with jupyter lab.
        runtype: Run type (jupyter, ssh, args).
        use_ssh: Supports ssh.
        jupyter_dir: Jupyter directory.
        docker_login_repo: Docker login repository.
        extra_filters: Search offer filters dict.
        disk_space: Recommended disk space.
        readme: Readme string.
        readme_visible: Whether readme is visible.
        desc: Description string.
        private: Whether template is private.

    Returns:
        Response dict with template info.
    """
    template = {
        "name": name,
        "image": image,
        "tag": image_tag,
        "href": href,
        "repo": repo,
        "env": env,
        "onstart": onstart_cmd,
        "jup_direct": jup_direct,
        "ssh_direct": ssh_direct,
        "use_jupyter_lab": use_jupyter_lab,
        "runtype": runtype,
        "use_ssh": use_ssh,
        "jupyter_dir": jupyter_dir,
        "docker_login_repo": docker_login_repo,
        "extra_filters": extra_filters or {},
        "recommended_disk_space": disk_space,
        "readme": readme,
        "readme_visible": readme_visible,
        "desc": desc,
        "private": private,
    }
    r = client.post("/template/", json_data=template)
    r.raise_for_status()
    return r.json()


def update_template(client: VastClient, hash_id: str, name: str = None,
                    image: str = None, image_tag: str = None, href: str = None,
                    repo: str = None, env: str = None, onstart_cmd: str = None,
                    jup_direct: bool = False, ssh_direct: bool = False,
                    use_jupyter_lab: bool = False, runtype: str = "args",
                    use_ssh: bool = False, jupyter_dir: str = None,
                    docker_login_repo: str = None, extra_filters: dict = None,
                    disk_space: float = None, readme: str = None,
                    readme_visible: bool = True, desc: str = None,
                    private: bool = True) -> dict:
    """Update an existing template.

    Args:
        client: VastClient instance.
        hash_id: Hash ID of the template to update.
        (remaining args same as create_template)

    Returns:
        Response dict with updated template info.
    """
    template = {
        "hash_id": hash_id,
        "name": name,
        "image": image,
        "tag": image_tag,
        "href": href,
        "repo": repo,
        "env": env,
        "onstart": onstart_cmd,
        "jup_direct": jup_direct,
        "ssh_direct": ssh_direct,
        "use_jupyter_lab": use_jupyter_lab,
        "runtype": runtype,
        "use_ssh": use_ssh,
        "jupyter_dir": jupyter_dir,
        "docker_login_repo": docker_login_repo,
        "extra_filters": extra_filters or {},
        "recommended_disk_space": disk_space,
        "readme": readme,
        "readme_visible": readme_visible,
        "desc": desc,
        "private": private,
    }
    r = client.put("/template/", json_data=template)
    r.raise_for_status()
    return r.json()


def delete_template(client: VastClient, hash_id: str = None,
                    template_id: int = None) -> dict:
    """Delete a template by hash_id or template_id.

    Args:
        client: VastClient instance.
        hash_id: Hash ID of the template to delete.
        template_id: Numeric ID of the template to delete.

    Returns:
        Response dict.
    """
    json_blob = {}
    if hash_id:
        json_blob["hash_id"] = hash_id
    elif template_id:
        json_blob["template_id"] = template_id
    r = client.delete("/template/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def launch_instance(client: VastClient, gpu_name: str, num_gpus: str, image: str,
                    region: str = None, disk: float = 10, order: str = "score-",
                    limit: int = None, env: dict = None, label: str = None,
                    extra: str = None, onstart_cmd: str = None, login: str = None,
                    python_utf8: bool = False, lang_utf8: bool = False,
                    jupyter_lab: bool = False, jupyter_dir: str = None,
                    cancel_unavail: bool = False,
                    template_hash: str = None, runtype: str = None,
                    args: str = None, query: dict = None,
                    ssh: bool = False, jupyter: bool = False,
                    direct: bool = False) -> dict:
    """Launch the top instance from search offers matching the given criteria.

    Searches for offers and launches the best match in a single API call.

    Args:
        client: VastClient instance.
        gpu_name: GPU model name (e.g. "RTX_4090").
        num_gpus: Number of GPUs required.
        image: Docker image to launch.
        region: Region name or country code list (e.g. "North_America" or "[US,CA]").
        disk: Disk space in GB (default 10).
        order: Sort order for offers (default "score-").
        limit: Max number of offers to consider.
        env: Environment variables dict.
        label: Instance label.
        extra: Extra docker options.
        onstart_cmd: Onstart script contents.
        login: Docker login credentials.
        python_utf8: Enable Python UTF-8 mode.
        lang_utf8: Enable lang UTF-8 mode.
        jupyter_lab: Launch with Jupyter Lab.
        jupyter_dir: Jupyter directory.
        cancel_unavail: Cancel if unavailable.
        template_hash: Template hash ID.
        runtype: Run type (jupyter, ssh, args).
        ssh: Launch as an ssh instance type.
        jupyter: Launch as a jupyter instance instead of an ssh instance.
        direct: Use (faster) direct connections for jupyter & ssh.
        args: Container arguments.
        query: Pre-built query dict (overrides auto-built query from gpu_name/num_gpus).

    Returns:
        Response dict with launch result.
    """
    if isinstance(env, str):
        env = parse_env(env)
    if template_hash is None:
        runtype, args = resolve_runtype(runtype, ssh=ssh, jupyter=jupyter,
                                        direct=direct, args=args,
                                        jupyter_lab=jupyter_lab,
                                        jupyter_dir=jupyter_dir)

    REGIONS = {
        "North_America": "[AG, BS, BB, BZ, CA, CR, CU, DM, DO, SV, GD, GT, HT, HN, JM, MX, NI, PA, KN, LC, VC, TT, US]",
        "South_America": "[AR, BO, BR, CL, CO, EC, FK, GF, GY, PY, PE, SR, UY, VE]",
        "Europe": "[AL, AD, AT, BY, BE, BA, BG, HR, CY, CZ, DK, EE, FI, FR, DE, GR, HU, IS, IE, IT, LV, LI, LT, LU, MT, MD, MC, ME, NL, MK, NO, PL, PT, RO, RU, SM, RS, SK, SI, ES, SE, CH, UA, GB, VA, XK]",
        "Asia": "[AF, AM, AZ, BH, BD, BT, BN, KH, CN, GE, IN, ID, IR, IQ, IL, JP, JO, KZ, KW, KG, LA, LB, MY, MV, MN, MM, NP, KP, OM, PK, PH, QA, SA, SG, KR, LK, SY, TW, TJ, TH, TL, TR, TM, AE, UZ, VN, YE, HK, MO]",
        "Oceania": "[AS, AU, CK, FJ, PF, GU, KI, MH, FM, NR, NC, NZ, NU, MP, PW, PG, PN, WS, SB, TK, TO, TV, VU, WF]",
        "Africa": "[DZ, AO, BJ, BW, BF, BI, CV, CM, CF, TD, KM, CG, CD, CI, DJ, EG, GQ, ER, SZ, ET, GA, GM, GH, GN, GW, KE, LS, LR, LY, MG, MW, ML, MR, MU, MA, MZ, NA, NE, NG, RW, ST, SN, SC, SL, SO, ZA, SS, SD, TZ, TG, TN, UG, ZM, ZW]",
    }

    if query is None:
        args_query = f"num_gpus={num_gpus} gpu_name={gpu_name}"
        if region:
            region_query = REGIONS.get(region, region)
            args_query += f" geolocation in {region_query}"
        if disk:
            args_query += f" disk_space>={disk}"
        base_query = {"verified": {"eq": True}, "external": {"eq": False},
                      "rentable": {"eq": True}, "rented": {"eq": False}}
        query = parse_query(args_query, base_query, offers_fields, offers_alias, offers_mult)

    # Parse order string
    order_list = parse_order(order) or []

    query["order"] = order_list
    query["type"] = "on-demand"
    if limit:
        query["limit"] = int(limit)
    query["allocated_storage"] = disk

    json_blob = {
        "image": image,
        "disk": disk,
        "q": query,
        "env": env or {},
        "label": label,
        "extra": extra,
        "onstart": onstart_cmd,
        "image_login": login,
        "python_utf8": python_utf8,
        "lang_utf8": lang_utf8,
        "use_jupyter_lab": jupyter_lab,
        "jupyter_dir": jupyter_dir,
        "cancel_unavail": cancel_unavail,
        "template_hash_id": template_hash,
    }
    if runtype:
        json_blob["runtype"] = runtype
    if args is not None:
        json_blob["args"] = args

    r = client.put("/launch_instance/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


