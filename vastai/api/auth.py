"""Auth, secrets, templates, scheduled jobs, and TFA API functions for the Vast.ai SDK."""


def show_audit_logs(client):
    """Display account's history of important actions.

    GET /audit_logs/

    Args:
        client: VastClient instance.

    Returns:
        list: Audit log entries.
    """
    r = client.get("/audit_logs/")
    r.raise_for_status()
    return r.json()


def show_env_vars(client):
    """Show user environment variables.

    GET /secrets/

    Args:
        client: VastClient instance.

    Returns:
        dict: Environment variables as key-value pairs.
    """
    r = client.get("/secrets/")
    r.raise_for_status()
    return r.json().get("secrets", {})


def create_env_var(client, name, value):
    """Create a new user environment variable.

    POST /secrets/

    Args:
        client: VastClient instance.
        name (str): Environment variable name.
        value (str): Environment variable value.

    Returns:
        dict: API response data.
    """
    data = {"key": name, "value": value}
    r = client.post("/secrets/", json_data=data)
    r.raise_for_status()
    return r.json()


def update_env_var(client, name, value):
    """Update an existing user environment variable.

    PUT /secrets/

    Args:
        client: VastClient instance.
        name (str): Environment variable name.
        value (str): New environment variable value.

    Returns:
        dict: API response data.
    """
    data = {"key": name, "value": value}
    r = client.put("/secrets/", json_data=data)
    r.raise_for_status()
    return r.json()


def delete_env_var(client, name):
    """Delete a user environment variable.

    DELETE /secrets/

    Args:
        client: VastClient instance.
        name (str): Environment variable name to delete.

    Returns:
        dict: API response data.
    """
    data = {"key": name}
    r = client.delete("/secrets/", json_data=data)
    r.raise_for_status()
    return r.json()


def show_scheduled_jobs(client):
    """Display the list of scheduled jobs.

    GET /commands/schedule_job/

    Args:
        client: VastClient instance.

    Returns:
        list: Scheduled job entries.
    """
    r = client.get("/commands/schedule_job/")
    r.raise_for_status()
    return r.json()


def create_scheduled_job(client, start_time, end_time, api_endpoint, request_method,
                         request_body, frequency, instance_id,
                         day_of_the_week=None, hour_of_the_day=None):
    """Create a new scheduled job.

    POST /commands/schedule_job/

    Args:
        client: VastClient instance.
        start_time (float): Start time as unix timestamp.
        end_time (float): End time as unix timestamp.
        api_endpoint (str): API endpoint the job will call.
        request_method (str): HTTP method (GET, POST, PUT, DELETE).
        request_body (dict): JSON body for the scheduled request.
        frequency (str): One of "HOURLY", "DAILY", "WEEKLY".
        instance_id (int): Instance ID the job is associated with.
        day_of_the_week (int, optional): Day of week (0=Sunday, 6=Saturday).
            Required for WEEKLY, must be None for HOURLY/DAILY.
        hour_of_the_day (int, optional): Hour of day (0-23).
            Required for DAILY/WEEKLY, must be None for HOURLY.

    Returns:
        dict: API response data.
    """
    json_blob = {
        "start_time": start_time,
        "end_time": end_time,
        "api_endpoint": api_endpoint,
        "request_method": request_method,
        "request_body": request_body,
        "day_of_the_week": day_of_the_week,
        "hour_of_the_day": hour_of_the_day,
        "frequency": frequency,
        "instance_id": instance_id,
    }
    r = client.post("/commands/schedule_job/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def update_scheduled_job(client, id, request_body, start_time=None, end_time=None,
                         api_endpoint=None, request_method=None,
                         frequency=None, instance_id=None,
                         day_of_the_week=None, hour_of_the_day=None):
    """Update an existing scheduled job.

    PUT /commands/schedule_job/{id}/

    Args:
        client: VastClient instance.
        id (int): ID of the scheduled job to update.
        request_body (dict): Updated JSON body for the scheduled request.
        start_time (float, optional): Updated start time as unix timestamp.
        end_time (float, optional): Updated end time as unix timestamp.
        api_endpoint (str, optional): Updated API endpoint.
        request_method (str, optional): Updated HTTP method.
        frequency (str, optional): Updated frequency (HOURLY, DAILY, WEEKLY).
        instance_id (int, optional): Updated instance ID.
        day_of_the_week (int, optional): Updated day of week.
        hour_of_the_day (int, optional): Updated hour of day.

    Returns:
        dict: API response data.
    """
    json_blob = {"request_body": request_body}
    if start_time is not None:
        json_blob["start_time"] = start_time
    if end_time is not None:
        json_blob["end_time"] = end_time
    if api_endpoint is not None:
        json_blob["api_endpoint"] = api_endpoint
    if request_method is not None:
        json_blob["request_method"] = request_method
    if frequency is not None:
        json_blob["frequency"] = frequency
    if instance_id is not None:
        json_blob["instance_id"] = instance_id
    if day_of_the_week is not None:
        json_blob["day_of_the_week"] = day_of_the_week
    if hour_of_the_day is not None:
        json_blob["hour_of_the_day"] = hour_of_the_day

    r = client.put(f"/commands/schedule_job/{id}/", json_data=json_blob)
    r.raise_for_status()
    return r.json()


def delete_scheduled_job(client, id):
    """Delete a scheduled job.

    DELETE /commands/schedule_job/{id}/

    Args:
        client: VastClient instance.
        id (int): ID of scheduled job to delete.

    Returns:
        dict: API response data.
    """
    r = client.delete(f"/commands/schedule_job/{id}/")
    r.raise_for_status()
    return r.json()


# --- Two-Factor Authentication (TFA) Functions ---


def _build_tfa_verification_payload(**kwargs):
    """Build common payload for TFA verification requests.

    Args:
        **kwargs: TFA verification fields including:
            tfa_method_id, tfa_method, code, backup_code, secret,
            and any additional fields.

    Returns:
        dict: Payload with only non-None values.
    """
    payload = {
        "tfa_method_id": kwargs.get("tfa_method_id"),
        "tfa_method": kwargs.get("tfa_method"),
        "code": kwargs.get("code"),
        "backup_code": kwargs.get("backup_code"),
        "secret": kwargs.get("secret"),
    }
    for key, value in kwargs.items():
        if key not in payload:
            payload[key] = value

    return {k: v for k, v in payload.items() if v is not None}


def tfa_activate(client, code, secret, method_type="totp", phone_number=None, label=None, method_id=None):
    """Activate a new 2FA method by verifying the code.

    POST /api/v0/tfa/test-submit/

    Args:
        client: VastClient instance.
        code (str): 6-digit verification code from SMS or Authenticator app.
        secret (str): Secret token from setup process.
        method_type (str): 2FA method type ('sms' or 'totp'). Default 'totp'.
        phone_number (str, optional): Phone number for SMS method (E.164 format).
        label (str, optional): Label for the new 2FA method.
        method_id (str, optional): 2FA Method ID if multiple of the same type.

    Returns:
        dict: API response data, may include backup_codes on first activation.
    """
    payload = _build_tfa_verification_payload(
        tfa_method_id=method_id,
        tfa_method=method_type,
        code=code,
        secret=secret,
        phone_number=phone_number,
        label=label,
    )

    r = client.post("/api/v0/tfa/test-submit/", json_data=payload)
    r.raise_for_status()
    return r.json()


def tfa_delete(client, code=None, backup_code=None, method_type=None, secret=None,
               method_id=None, id_to_delete=None):
    """Remove a 2FA method from your account.

    DELETE /api/v0/tfa/

    Requires 2FA verification to prevent unauthorized removals.

    Args:
        client: VastClient instance.
        code (str, optional): 2FA code from Authenticator app, SMS, or Email.
        backup_code (str, optional): One-time backup code (alternative to code).
        method_type (str, optional): 2FA method type ('email', 'sms', 'totp').
        secret (str, optional): Secret token (required for SMS or Email).
        method_id (str, optional): 2FA Method ID.
        id_to_delete (int, optional): ID of the 2FA method to delete.

    Returns:
        dict: API response data including remaining_methods count.
    """
    payload = _build_tfa_verification_payload(
        tfa_method_id=method_id,
        tfa_method=method_type,
        code=code,
        backup_code=backup_code,
        secret=secret,
        target_id=id_to_delete,
    )

    r = client.delete("/api/v0/tfa/", json_data=payload)
    r.raise_for_status()
    return r.json()


def tfa_login(client, code=None, backup_code=None, method_type=None, secret=None, method_id=None):
    """Complete 2FA login by verifying code.

    POST /api/v0/tfa/

    Args:
        client: VastClient instance.
        code (str, optional): 2FA code from Authenticator app, SMS, or Email.
        backup_code (str, optional): One-time backup code (alternative to code).
        method_type (str, optional): 2FA method type ('email', 'sms', 'totp').
        secret (str, optional): Secret token (required for SMS or Email).
        method_id (str, optional): 2FA Method ID.

    Returns:
        dict: API response data including session_key and
            backup_codes_remaining.
    """
    payload = _build_tfa_verification_payload(
        tfa_method_id=method_id,
        tfa_method=method_type,
        code=code,
        backup_code=backup_code,
        secret=secret,
    )

    r = client.post("/api/v0/tfa/", json_data=payload)
    r.raise_for_status()
    return r.json()


def tfa_resend_sms(client, secret, phone_number=None):
    """Resend SMS 2FA code.

    POST /api/v0/tfa/resend/

    Args:
        client: VastClient instance.
        secret (str): Secret token from the original 2FA request.
        phone_number (str, optional): Phone number to receive SMS code
            (E.164 format).

    Returns:
        dict: API response data.
    """
    payload = _build_tfa_verification_payload(
        secret=secret,
        phone_number=phone_number,
    )

    r = client.post("/api/v0/tfa/resend/", json_data=payload)
    r.raise_for_status()
    return r.json()


def tfa_regen_codes(client, code=None, backup_code=None, method_type=None, secret=None, method_id=None):
    """Regenerate backup codes for 2FA.

    PUT /api/v0/tfa/regen-backup-codes/

    Warning: This will invalidate all existing backup codes.

    Args:
        client: VastClient instance.
        code (str, optional): 2FA code from Authenticator app, SMS, or Email.
        backup_code (str, optional): One-time backup code (alternative to code).
        method_type (str, optional): 2FA method type ('email', 'sms', 'totp').
        secret (str, optional): Secret token (required for SMS or Email).
        method_id (str, optional): 2FA Method ID.

    Returns:
        dict: API response data including new backup_codes list.
    """
    payload = _build_tfa_verification_payload(
        tfa_method_id=method_id,
        tfa_method=method_type,
        code=code,
        backup_code=backup_code,
        secret=secret,
    )

    r = client.put("/api/v0/tfa/regen-backup-codes/", json_data=payload)
    r.raise_for_status()
    return r.json()


def tfa_send_sms(client, phone_number=None):
    """Request a 2FA SMS verification code.

    POST /api/v0/tfa/test/

    Args:
        client: VastClient instance.
        phone_number (str, optional): Phone number to receive SMS code
            (E.164 format). If not provided, uses account phone number.

    Returns:
        dict: API response data including secret token.
    """
    payload = {}
    if phone_number:
        payload["phone_number"] = phone_number

    r = client.post("/api/v0/tfa/test/", json_data=payload)
    r.raise_for_status()
    return r.json()


def tfa_status(client):
    """Show the current 2FA status and configured methods.

    GET /tfa/status/

    Args:
        client: VastClient instance.

    Returns:
        dict: 2FA status including tfa_enabled, methods list,
            and backup_codes_remaining.
    """
    r = client.get("/tfa/status/")
    r.raise_for_status()
    return r.json()


def tfa_totp_setup(client):
    """Generate TOTP secret and QR code for Authenticator app setup.

    POST /api/v0/tfa/totp-setup/

    Args:
        client: VastClient instance.

    Returns:
        dict: Setup data including secret and provisioning_uri.
    """
    r = client.post("/api/v0/tfa/totp-setup/", json_data={})
    r.raise_for_status()
    return r.json()


def tfa_update(client, method_id, label=None, set_primary=None):
    """Update a 2FA method's settings.

    PUT /api/v0/tfa/update/

    Args:
        client: VastClient instance.
        method_id (int): ID of the 2FA method to update.
        label (str, optional): New label/name for this 2FA method.
        set_primary (bool, optional): Set this method as the primary
            2FA method.

    Returns:
        dict: API response data including updated method info.

    Raises:
        ValueError: If neither label nor set_primary is provided.
    """
    payload = {"tfa_method_id": method_id}

    if label is not None:
        payload["label"] = label
    if set_primary is not None:
        payload["is_primary"] = set_primary

    if len(payload) == 1:
        raise ValueError("Must specify at least one field to update (label or set_primary)")

    r = client.put("/api/v0/tfa/update/", json_data=payload)
    r.raise_for_status()
    return r.json()


def tfa_auth_new(client, code=None, secret=None, backup_code=None,
                 method_type="email", method_id=None):
    """Authorize account to add a new 2FA method.

    POST/PUT /api/v0/tfa/authorize-new-method/

    Args:
        client: VastClient instance.
        code (str, optional): 2FA verification code.
        secret (str, optional): Secret token from previous auth step.
        backup_code (str, optional): One-time backup code.
        method_type (str): 2FA method type ('email', 'sms', 'totp').
        method_id (str, optional): Specific method ID to use.

    Returns:
        dict: API response data.
    """
    url = "/api/v0/tfa/authorize-new-method/"

    if secret and code:
        payload = {"secret": secret, "code": code}
        r = client.put(url, json_data=payload)
        r.raise_for_status()
        return r.json()

    payload = {}
    if backup_code:
        payload["backup_code"] = backup_code
    elif method_id:
        payload["tfa_method_id"] = method_id
    elif method_type:
        payload["tfa_method"] = method_type

    r = client.post(url, json_data=payload)
    r.raise_for_status()
    return r.json()


def tfa_send_email(client):
    """Request a 2FA email verification code.

    POST /api/v0/tfa/email/

    Args:
        client: VastClient instance.

    Returns:
        dict: API response data including secret token.
    """
    r = client.post("/api/v0/tfa/email/", json_data={})
    r.raise_for_status()
    return r.json()
