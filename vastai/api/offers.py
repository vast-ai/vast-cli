"""Search offers, templates, benchmarks, volumes, network volumes, and invoices."""
from vastai.api.client import VastClient


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


def search_benchmarks(client: VastClient, query: dict = None) -> list:
    """Search for benchmarks using a query dict.

    Args:
        client: VastClient instance.
        query: Pre-parsed query dict of select_filters.

    Returns:
        List of benchmark dicts.
    """
    query_args = {"select_cols": ["*"], "select_filters": query or {}}
    r = client.get("/benchmarks", query_args=query_args)
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
                    force: bool = False, cancel_unavail: bool = False,
                    template_hash: str = None, runtype: str = None,
                    args: str = None, query: dict = None) -> dict:
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
        force: Force launch even if offer is unavailable.
        cancel_unavail: Cancel if unavailable.
        template_hash: Template hash ID.
        runtype: Run type (jupyter, ssh, args).
        args: Container arguments.
        query: Pre-built query dict (overrides auto-built query from gpu_name/num_gpus).

    Returns:
        Response dict with launch result.
    """
    from vastai.api.query import parse_query, offers_fields, offers_alias, offers_mult

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
    order_list = []
    if isinstance(order, str):
        for name in order.split(","):
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
            order_list.append([field, direction])
    elif isinstance(order, list):
        order_list = order

    query["order"] = order_list
    query["type"] = "on-demand"
    if limit:
        query["limit"] = int(limit)
    query["allocated_storage"] = disk

    json_blob = {
        "client_id": "me",
        "gpu_name": gpu_name,
        "num_gpus": num_gpus,
        "region": region,
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
        "force": force,
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


