"""Billing, user, and account API functions for the Vast.ai SDK."""

import time


def show_invoices(client, start_date=None, end_date=None, only_charges=False, only_credits=False):
    """Get billing history reports (deprecated endpoint).

    GET /users/me/invoices

    Args:
        client: VastClient instance.
        start_date (str, optional): Start date/time for report.
        end_date (str, optional): End date/time for report.
        only_charges (bool): Show only charge items. Default False.
        only_credits (bool): Show only credit items. Default False.

    Returns:
        dict: Invoice data including 'invoices' and 'current' charges.
    """
    Minutes = 60.0
    Hours = 60.0 * Minutes
    Days = 24.0 * Hours

    end_timestamp = time.time()
    start_timestamp = time.time() - (24 * 60 * 60)

    try:
        import dateutil
        from dateutil import parser as dateutil_parser

        if end_date:
            try:
                parsed_end = dateutil_parser.parse(str(end_date))
                end_timestamp = parsed_end.timestamp()
            except ValueError:
                pass

        if start_date:
            try:
                parsed_start = dateutil_parser.parse(str(start_date))
                start_timestamp = parsed_start.timestamp()
            except ValueError:
                pass
    except ImportError:
        pass

    sdate = start_timestamp
    edate = end_timestamp

    query_args = {
        "owner": "me",
        "sdate": sdate,
        "edate": edate,
        "inc_charges": not only_credits,
    }

    r = client.get("/users/me/invoices", query_args=query_args)
    r.raise_for_status()
    rj = r.json()

    rows = rj["invoices"]
    current_charges = rj["current"]

    if only_charges:
        rows = [row for row in rows if row.get("type") == "charge"]
    elif only_credits:
        rows = [row for row in rows if row.get("type") == "payment"]

    return {
        "invoices": rows,
        "current": current_charges,
    }


def show_invoices_v1(client, params):
    """Get billing (invoices/charges) history reports with advanced filtering.

    GET /api/v0/charges/ (for charges) or /api/v1/invoices/ (for invoices)

    Args:
        client: VastClient instance.
        params (dict): Request parameters including:
            charges (bool): If True, fetch charges; otherwise fetch invoices.
            start_date (int/str, optional): Start date (YYYY-MM-DD or timestamp).
            end_date (int/str, optional): End date (YYYY-MM-DD or timestamp).
            limit (int): Number of results per page. Default 20, max 100.
            next_token (str, optional): Pagination token for next page.
            latest_first (bool): Sort by latest first. Default False.
            charge_type (list, optional): Filter charge types (instance, volume, serverless).
            invoice_type (list, optional): Filter invoice types.
            format (str): Output format (table or tree). Default 'table'.

    Returns:
        dict: API response with 'results', 'count', 'total', and 'next_token'.
    """
    from datetime import datetime, timezone

    invoice_types_map = {
        "transfers": "transfer",
        "stripe": "stripe_payments",
        "bitpay": "bitpay",
        "coinbase": "coinbase",
        "crypto.com": "crypto.com",
        "reserved": "instance_prepay",
        "payout_paypal": "paypal_manual",
        "payout_wise": "wise_manual",
    }

    is_charges = params.get("charges", False)
    start_date = params.get("start_date")
    end_date = params.get("end_date")

    # Handle default start and end date values
    if not start_date and not end_date:
        end_date = int(time.time())
    if not start_date:
        end_date_val = end_date if isinstance(end_date, int) else int(
            datetime.strptime(str(end_date) + "+0000", '%Y-%m-%d%z').timestamp()
            if isinstance(end_date, str) and not str(end_date).isdigit()
            else int(end_date)
        )
        start_date = end_date_val - 7 * 24 * 60 * 60
    elif not end_date:
        start_date_val = start_date if isinstance(start_date, int) else int(
            datetime.strptime(str(start_date) + "+0000", '%Y-%m-%d%z').timestamp()
            if isinstance(start_date, str) and not str(start_date).isdigit()
            else int(start_date)
        )
        end_date = start_date_val + 7 * 24 * 60 * 60

    def to_timestamp(val):
        if isinstance(val, int):
            return val
        if isinstance(val, str):
            if val.isdigit():
                return int(val)
            return int(datetime.strptime(val + "+0000", '%Y-%m-%d%z').timestamp())
        raise ValueError("Invalid date format")

    start_timestamp = to_timestamp(start_date)
    end_timestamp = to_timestamp(end_date)

    # Build request parameters
    date_col = 'day' if is_charges else 'when'
    query_params = {
        'select_filters': {date_col: {'gte': start_timestamp, 'lte': end_timestamp}},
        'latest_first': params.get('latest_first', False),
        'limit': min(params.get('limit', 20), 100),
    }

    if is_charges:
        query_params['format'] = params.get('format', 'table')
        charge_types = params.get('charge_type', [])
        for ct in charge_types:
            filters = query_params['select_filters'].setdefault('type', {}).setdefault('in', [])
            if ct in {'i', 'instance'}:
                filters.append('instance')
            elif ct in {'v', 'volume'}:
                filters.append('volume')
            elif ct in {'s', 'serverless'}:
                filters.append('serverless')
    else:
        invoice_type_list = params.get('invoice_type', [])
        for it in invoice_type_list:
            filters = query_params['select_filters'].setdefault('service', {}).setdefault('in', [])
            if it in invoice_types_map:
                filters.append(invoice_types_map[it])

    next_token = params.get('next_token')
    if next_token:
        query_params['after_token'] = next_token

    endpoint = '/api/v0/charges/' if is_charges else '/api/v1/invoices/'
    r = client.get(endpoint, query_args=query_params)
    r.raise_for_status()
    return r.json()


def show_earnings(client, start_date=None, end_date=None, machine_id=None):
    """Get machine earning history reports.

    GET /users/me/machine-earnings

    Args:
        client: VastClient instance.
        start_date (str, optional): Start date/time for report.
        end_date (str, optional): End date/time for report.
        machine_id (int, optional): Machine ID to filter by.

    Returns:
        dict/list: Earnings data from the API.
    """
    Minutes = 60.0
    Hours = 60.0 * Minutes
    Days = 24.0 * Hours
    cday = time.time() / Days
    sday = cday - 1.0
    eday = cday - 1.0

    try:
        import dateutil
        from dateutil import parser as dateutil_parser

        if end_date:
            try:
                parsed_end = dateutil_parser.parse(str(end_date))
                eday = parsed_end.timestamp() / Days
            except ValueError:
                pass

        if start_date:
            try:
                parsed_start = dateutil_parser.parse(str(start_date))
                sday = parsed_start.timestamp() / Days
            except ValueError:
                pass
    except ImportError:
        pass

    query_args = {
        "owner": "me",
        "sday": sday,
        "eday": eday,
        "machid": machine_id,
    }

    r = client.get("/users/me/machine-earnings", query_args=query_args)
    r.raise_for_status()
    return r.json()


def show_deposit(client, id):
    """Display reserve deposit info for an instance.

    GET /instances/balance/{id}/

    Args:
        client: VastClient instance.
        id (int): ID of instance to get deposit info for.

    Returns:
        dict: Deposit/balance information.
    """
    r = client.get(f"/instances/balance/{id}/", query_args={"owner": "me"})
    r.raise_for_status()
    return r.json()


def show_user(client):
    """Get current user data.

    GET /users/current

    Args:
        client: VastClient instance.

    Returns:
        dict: User data (with api_key removed).
    """
    r = client.get("/users/current", query_args={"owner": "me"})
    r.raise_for_status()
    user_blob = r.json()
    user_blob.pop("api_key", None)
    return user_blob


def set_user(client, params):
    """Update current user settings.

    PUT /users/

    Args:
        client: VastClient instance.
        params (dict): User settings to update. Possible keys include:
            ssh_key, api_key, billaddress_name, billaddress_addr1,
            billaddress_addr2, billaddress_city, billaddress_zip,
            billaddress_country, billaddress_taxinfo,
            balance_threshold_enabled, balance_threshold,
            autobill_threshold, phone_number.

    Returns:
        dict: API response data.
    """
    r = client.put("/users/", json_data=params)
    r.raise_for_status()
    return r.json()


def show_subaccounts(client):
    """Get current subaccounts.

    GET /subaccounts

    Args:
        client: VastClient instance.

    Returns:
        list: Subaccount user data.
    """
    r = client.get("/subaccounts", query_args={"owner": "me"})
    r.raise_for_status()
    return r.json()["users"]


def create_subaccount(client, email, username, password, host_only=False):
    """Create a subaccount.

    POST /users/

    Args:
        client: VastClient instance.
        email (str): Email address for the subaccount.
        username (str): Username for the subaccount.
        password (str): Password for the subaccount.
        host_only (bool): If True, create as host-only account. Default False.

    Returns:
        dict: API response data.
    """
    json_blob = {
        "email": email,
        "username": username,
        "password": password,
        "host_only": host_only,
        "parent_id": "me",
    }

    r = client.post("/users/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def fetch_contracts(client, label=None, contract_ids=None):
    """Fetch contracts, optionally filtered by label.

    POST /contracts/fetch/

    Args:
        client: VastClient instance.
        label (str, optional): Instance label to filter by.
        contract_ids (list, optional): List of contract IDs to filter.

    Returns:
        list: Matching contract dicts.
    """
    json_blob = {}
    if label is not None:
        json_blob["label"] = label
    if contract_ids is not None:
        json_blob["contract_ids"] = list(contract_ids)
    r = client.post("/contracts/fetch/", json_data=json_blob)
    r.raise_for_status()
    return r.json()["contracts"]


def show_ipaddrs(client):
    """Display user's history of IP addresses.

    GET /users/me/ipaddrs

    Args:
        client: VastClient instance.

    Returns:
        list: IP address access history.
    """
    r = client.get("/users/me/ipaddrs", query_args={"owner": "me"})
    r.raise_for_status()
    return r.json()["results"]
