"""CLI commands for authentication and 2FA."""

import json
import os
import sys
from datetime import datetime

from vastai.cli.parser import argument
from vastai.cli.display import deindent, display_table
from vastai.api import auth as auth_api
from vastai.cli.util import SUCCESS, WARN, FAIL


# ---------------------------------------------------------------------------
# TFA helper functions (ported from old/vast.py)
# ---------------------------------------------------------------------------

TFA_METHOD_FIELDS = (
    ("id", "ID", "{}", None, True),
    ("user_id", "User ID", "{}", None, True),
    ("is_primary", "Primary", "{}", None, True),
    ("method", "Method", "{}", None, True),
    ("label", "Label", "{}", None, True),
    ("phone_number", "Phone Number", "{}", None, False),
    ("created_at", "Created", "{}", lambda x: datetime.fromtimestamp(x).strftime('%Y-%m-%d %H:%M:%S') if x else "N/A", True),
    ("last_used", "Last Used", "{}", lambda x: datetime.fromtimestamp(x).strftime('%Y-%m-%d %H:%M:%S') if x else "Never", True),
    ("fail_count", "Failures", "{}", None, True),
    ("locked_until", "Locked Until", "{}", lambda x: datetime.fromtimestamp(x).strftime('%Y-%m-%d %H:%M:%S') if x else "N/A", True),
)


def display_tfa_methods(methods):
    """Helper function to display 2FA methods in a table."""
    method_fields = TFA_METHOD_FIELDS
    has_sms = any(m['method'] == 'sms' for m in methods)
    if not has_sms:  # Don't show Phone Number column if the user has no SMS methods
        method_fields = tuple(field for field in TFA_METHOD_FIELDS if field[0] != 'phone_number')
    display_table(methods, method_fields, replace_spaces=False)


def confirm_destructive_action(prompt="Are you sure? (y/n): "):
    """Prompt user for confirmation of destructive actions."""
    try:
        response = input(f" {prompt}").strip().lower()
        return 'y' in response
    except (EOFError, KeyboardInterrupt):
        print("\nOperation cancelled.")
        raise


def handle_failed_tfa_verification(args, e):
    """Parse TFA error responses and provide contextual error messages."""
    try:
        error_data = e.response.json()
    except Exception:
        print(f"\n{FAIL} Error: {e}")
        return

    error_msg = error_data.get("msg", str(e))
    error_code = error_data.get("error", "")

    if args.raw:
        print(json.dumps(error_data, indent=2))

    print(f"\n{FAIL} Error: {error_msg}")

    # Provide helpful context for common errors
    if error_code in {"tfa_locked", "2fa_verification_failed"}:
        fail_count = error_data.get("fail_count", 0)
        locked_until = error_data.get("locked_until")

        if fail_count > 0:
            print(f"   Failed attempts: {fail_count}")
        if locked_until:
            lock_time_sec = (datetime.fromtimestamp(locked_until) - datetime.now()).seconds
            minutes, seconds = divmod(lock_time_sec, 60)
            print(f"   Time Remaining for 2FA Lock: {minutes} minutes and {seconds} seconds...")

    elif error_code == "2fa_expired":
        # Note: Only SMS uses tfa challenges that expire when verifying
        print("\n   The SMS code and secret have expired. Please start over:")
        print("     vastai tfa send-sms")


def format_backup_codes(backup_codes):
    """Format backup codes for display or file output."""
    output_lines = [
        "=" * 60, "  VAST.AI 2FA BACKUP CODES", "=" * 60,
        f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"\n{WARN}  WARNING: All previous backup codes are now invalid!",
        "\nYour New Backup Codes (one-time use only):",
        "-" * 40,
    ]
    for i, code in enumerate(backup_codes, 1):
        output_lines.append(f"  {i:2d}. {code}")
    output_lines.extend([
        "-" * 40,
        "\nIMPORTANT:",
        " \u2022 Each code can only be used once",
        " \u2022 Store them in a secure location",
        " \u2022 Use these codes to log in if you lose access to your 2FA device",
        "\n" + "=" * 60,
    ])
    return "\n".join(output_lines)


def _save_to_file(content, filepath):
    """Save content to file, creating parent directories if needed."""
    try:
        filepath = os.path.abspath(os.path.expanduser(filepath))
        parent_dir = os.path.dirname(filepath)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(filepath, "w") as f:
            f.write(content)
        return True
    except (IOError, OSError) as e:
        print(f"\n{FAIL} Error saving file: {e}")
        return False


def _get_backup_codes_filename():
    """Generate a timestamped filename for backup codes."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"vastai_backup_codes_{timestamp}.txt"


def save_backup_codes(backup_codes):
    """Save or display 2FA backup codes based on user choice."""
    print(f"\nBackup codes regenerated successfully! {SUCCESS}")
    print(f"\n{WARN}  WARNING: All previous backup codes are now invalid!")

    formatted_content = format_backup_codes(backup_codes)
    filename = _get_backup_codes_filename()

    while True:
        print("\nHow would you like to save your new backup codes?")
        print(f"  1. Save to default location (~/Downloads/{filename})")
        print(f"  2. Save to a custom path")
        print(f"  3. Print to screen ({WARN}  potentially unsafe - visible to onlookers)")

        try:
            choice = input("\nEnter choice (1-3): ").strip()

            if choice in {'1', '2'}:
                if choice == '1':
                    downloads_dir = os.path.expanduser("~/Downloads")
                    filepath = os.path.join(downloads_dir, filename)
                else:  # choice == '2'
                    custom_path = input("\nEnter full path for backup codes file: ").strip()
                    if not custom_path:
                        print("Error: Path cannot be empty")
                        continue

                    filepath = os.path.abspath(os.path.expanduser(custom_path))
                    if os.path.isdir(filepath):
                        filepath = os.path.join(filepath, filename)

                if _save_to_file(formatted_content, filepath):
                    print(f"\n{SUCCESS} Backup codes saved to: {filepath}")
                    print(f"\nIMPORTANT:")
                    print(f" \u2022 The file contains {len(backup_codes)} one-time use backup codes")
                    if choice == '1':
                        print(f" \u2022 Move this file to a secure location")
                    return
                else:
                    print("Please try again with a different path.")
                    continue

            elif choice == '3':
                print(f"\n{WARN}  WARNING: Printing sensitive codes to screen!")
                confirm = input("\nAre you sure? Anyone nearby can see these codes. (yes/no): ").strip().lower()
                if confirm in {'yes', 'y'}:
                    print("\n" + formatted_content + "\n")
                    return
                else:
                    print("Cancelled. Please choose another option.")
                    continue

            else:
                print("Invalid choice. Please enter 1, 2, or 3.")

        except (EOFError, KeyboardInterrupt):
            print("\n\nOperation cancelled. Your backup codes were generated but not saved.")
            print("You will need to regenerate them to get new codes.")
            raise


from vastai.cli.utils import get_parser as _get_parser, get_client  # noqa: F401


parser = _get_parser()


# ---------------------------------------------------------------------------
# set api-key
# ---------------------------------------------------------------------------

@parser.command(
    argument("new_api_key", help="Api key to set as currently logged in user"),
    usage="vastai set api-key APIKEY",
    help="Set api-key (get your api-key from the console/CLI)",
)
def set__api_key(args):
    """Set the api-key."""
    from vastai.cli.util import APIKEY_FILE, APIKEY_FILE_HOME

    with open(APIKEY_FILE, "w") as writer:
        writer.write(args.new_api_key)
    print("Your api key has been saved in {}".format(APIKEY_FILE))

    if os.path.exists(APIKEY_FILE_HOME):
        os.remove(APIKEY_FILE_HOME)
        print("Your api key has been removed from {}".format(APIKEY_FILE_HOME))


# ---------------------------------------------------------------------------
# Note: set__user and show__user are in billing.py.
# Note: show__ipaddrs is in billing.py.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# show audit-logs
# ---------------------------------------------------------------------------

@parser.command(
    usage="vastai show audit-logs [--api-key API_KEY] [--raw]",
    help="Display account's history of important actions",
)
def show__audit_logs(args):
    """Show the history of important actions."""
    from vastai.cli.display import display_table, audit_log_fields
    client = get_client(args)
    rows = auth_api.show_audit_logs(client)
    if args.raw:
        return rows
    else:
        display_table(rows, audit_log_fields)


# ---------------------------------------------------------------------------
# environment variables
# ---------------------------------------------------------------------------

@parser.command(
    argument("-s", "--show-values", action="store_true", help="Show the values of environment variables"),
    usage="vastai show env-vars [-s]",
    help="Show user environment variables",
)
def show__env_vars(args):
    """Show the environment variables for the current user."""
    client = get_client(args)
    env_vars = auth_api.show_env_vars(client)

    if args.raw:
        if not args.show_values:
            masked_env_vars = {k: "*****" for k, v in env_vars.items()}
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
    argument("name", help="Environment variable name", type=str),
    argument("value", help="Environment variable value", type=str),
    usage="vastai create env-var <name> <value>",
    help="Create a new user environment variable",
)
def create__env_var(args):
    """Create a new environment variable for the current user."""
    client = get_client(args)
    result = auth_api.create_env_var(client, name=args.name, value=args.value)

    if result.get("success"):
        print(result.get("msg", "Environment variable created successfully."))
    else:
        print(f"Failed to create environment variable: {result.get('msg', 'Unknown error')}")


@parser.command(
    argument("name", help="Environment variable name to update", type=str),
    argument("value", help="New environment variable value", type=str),
    usage="vastai update env-var <name> <value>",
    help="Update an existing user environment variable",
)
def update__env_var(args):
    """Update an existing environment variable for the current user."""
    client = get_client(args)
    result = auth_api.update_env_var(client, name=args.name, value=args.value)

    if result.get("success"):
        print(result.get("msg", "Environment variable updated successfully."))
    else:
        print(f"Failed to update environment variable: {result.get('msg', 'Unknown error')}")


@parser.command(
    argument("name", help="Environment variable name to delete", type=str),
    usage="vastai delete env-var <name>",
    help="Delete a user environment variable",
)
def delete__env_var(args):
    """Delete an environment variable for the current user."""
    client = get_client(args)
    result = auth_api.delete_env_var(client, name=args.name)

    if result.get("success"):
        print(result.get("msg", "Environment variable deleted successfully."))
    else:
        print(f"Failed to delete environment variable: {result.get('msg', 'Unknown error')}")


# ---------------------------------------------------------------------------
# Note: show__scheduled_jobs and delete__scheduled_job are in billing.py.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 2FA commands
# ---------------------------------------------------------------------------

@parser.command(
    argument("code", help="6-digit verification code from SMS or Authenticator app", type=str),
    argument("-t", "--method-type", choices=["sms", "totp"], help="New 2FA Method type to activate", type=str, default="totp"),
    argument("--secret", help="Secret token from setup process (required)", type=str, required=True),
    argument("--phone-number", help="Phone number for SMS method (E.164 format)", type=str, default=None),
    argument("-l", "--label", help="Label for the new 2FA method", type=str, default=None),
    usage="vastai tfa activate CODE --secret SECRET [--method-type {sms,totp}] [--phone-number PHONE_NUMBER] [--label LABEL]",
    help="Activate a new 2FA method by verifying the code",
)
def tfa__activate(args):
    """Activate a new 2FA method by confirming the verification code."""
    client = get_client(args)
    response_data = auth_api.tfa_activate(
        client, code=args.code, secret=args.secret, method_type=args.method_type,
        phone_number=args.phone_number, label=args.label,
    )
    method_name = "SMS" if args.phone_number or args.method_type == "sms" else "TOTP (Authenticator App)"
    print(f"\n{SUCCESS} {method_name} 2FA method activated successfully!")
    if "backup_codes" in response_data:
        save_backup_codes(response_data["backup_codes"])


@parser.command(
    argument("-id", "--id-to-delete", help="ID of the 2FA method to delete (see `vastai tfa status`)", type=int, default=None),
    argument("-c", "--code", mutex_group='code_grp', required=True, help="2FA code from your Authenticator app, SMS, or Email to authorize deletion", type=str),
    argument("-t", "--method-type", mutex_group="type_grp", choices=["email", "sms", "totp"],
             help="2FA Method type. Only use when you only have one method of this type", type=str, default=None),
    argument("-s", "--secret", help="Secret token (required for SMS or Email 2FA)", type=str, default=None),
    argument("-bc", "--backup-code", mutex_group='code_grp', required=True, help="One-time backup code (alternative to regular 2FA code)", type=str, default=None),
    argument("--method-id", mutex_group="type_grp", help="2FA Method ID to use if you have more than one of the same type ('id' from `tfa status`)", type=str, default=None),
    usage="vastai tfa delete [--id-to-delete ID] [--code CODE | --backup-code CODE] [--method-type {email,sms,totp}]",
    help="Remove a 2FA method from your account",
)
def tfa__delete(args):
    """Remove a 2FA method from the user's account."""
    if args.method_type in ("sms", "email") and not args.secret:
        print(f"\n{FAIL} Error: --secret is required for deletion authorization when using --method-type {args.method_type}.")
        print("\nPlease use:  `vastai tfa send-sms` or `vastai tfa send-email` to get the missing secret and try again.")
        return 1

    prompt = "\nAre you sure you want to delete this 2FA method? (y|n): "
    if confirm_destructive_action(prompt) == False:
        print("Operation cancelled.")
        return

    client = get_client(args)
    try:
        response_data = auth_api.tfa_delete(
            client, code=args.code, backup_code=args.backup_code,
            method_type=args.method_type, secret=args.secret, method_id=args.method_id,
            id_to_delete=args.id_to_delete,
        )
        print(f"\n{SUCCESS} 2FA method deleted successfully.")

        if "remaining_methods" in response_data:
            remaining = response_data["remaining_methods"]
            print(f"\nYou have {remaining} 2FA method{'s' if remaining != 1 else ''} remaining.")
        else:
            print(f"\n{WARN}  WARNING: You have removed all 2FA methods from your account.")
            print("Your backup codes have been invalidated and 2FA is now fully disabled.")

    except Exception as e:
        if hasattr(e, 'response'):
            handle_failed_tfa_verification(args, e)
        else:
            print(f"Failed to delete 2FA method: {e}")
        return 1


@parser.command(
    argument("-c", "--code", mutex_group='code_grp', required=True, help="2FA code from Authenticator app, SMS, or Email", type=str),
    argument("-t", "--method-type", mutex_group="type_grp", choices=["email", "sms", "totp"],
             help="2FA Method type. Only use when you only have one method of this type", type=str, default=None),
    argument("-s", "--secret", help="Secret token from previous login step (required for SMS or Email 2FA)", type=str, default=None),
    argument("-bc", "--backup-code", mutex_group='code_grp', required=True, help="One-time backup code (alternative to regular 2FA code)", type=str, default=None),
    argument("-id", "--method-id", mutex_group="type_grp", help="2FA Method ID if you have more than one of the same type ('id' from `tfa status`)", type=str, default=None),
    usage="vastai tfa login [--code CODE | --backup-code CODE] [--method-type {email,sms,totp}] [--secret SECRET]",
    help="Complete 2FA login by verifying code",
)
def tfa__login(args):
    """Complete 2FA login and store the session key."""
    from vastai.cli.util import TFAKEY_FILE

    client = get_client(args)
    try:
        response_data = auth_api.tfa_login(
            client, code=args.code, backup_code=args.backup_code,
            method_type=args.method_type, secret=args.secret, method_id=args.method_id,
        )

        if "session_key" in response_data:
            session_key = response_data["session_key"]
            if session_key != args.api_key:
                with open(TFAKEY_FILE, "w") as f:
                    f.write(session_key)
                print(f"{SUCCESS} 2FA login successful! Session key saved to {TFAKEY_FILE}")
            else:
                print(f"{SUCCESS} 2FA login successful! Your session key has been refreshed.")

            # Display remaining backup codes if present
            if "backup_codes_remaining" in response_data:
                remaining = response_data["backup_codes_remaining"]
                if remaining == 0:
                    print(f"{WARN}  Warning: You have no backup codes remaining! Please generate new backup codes immediately to avoid being locked out of your account if you lose access to your 2FA device.")
                elif remaining <= 3:
                    print(f"{WARN}  Warning: You only have {remaining} backup codes remaining. Consider regenerating them.")
                else:
                    print(f"Backup codes remaining: {remaining}")
        else:
            print("2FA login successful but a session key was not returned. Please check that you have an API Key that's properly set up")
    except Exception as e:
        if hasattr(e, 'response'):
            handle_failed_tfa_verification(args, e)
        else:
            print(f"2FA login failed: {e}")
        return 1


@parser.command(
    argument("-p", "--phone-number", help="Phone number to receive SMS code (E.164 format)", type=str, default=None),
    argument("-s", "--secret", help="Secret token from the original 2FA login attempt", type=str, required=True),
    usage="vastai tfa resend-sms --secret SECRET [--phone-number PHONE_NUMBER]",
    help="Resend SMS 2FA code",
)
def tfa__resend_sms(args):
    """Resend SMS 2FA code to the user's phone."""
    client = get_client(args)
    response_data = auth_api.tfa_resend_sms(client, secret=args.secret, phone_number=args.phone_number)
    print("SMS code resent successfully!")
    print(f"\n{response_data['msg']}")


@parser.command(
    argument("-c", "--code", mutex_group='code_grp', required=True, help="2FA code from Authenticator app, SMS, or Email", type=str),
    argument("-t", "--method-type", mutex_group="type_grp", choices=["email", "sms", "totp"],
             help="2FA Method type. Only use when you only have one method of this type", type=str, default=None),
    argument("-s", "--secret", help="Secret token from previous login step (required for SMS or Email 2FA)", type=str, default=None),
    argument("-bc", "--backup-code", mutex_group='code_grp', required=True, help="One-time backup code (alternative to regular 2FA code)", type=str, default=None),
    argument("-id", "--method-id", mutex_group="type_grp", help="2FA Method ID if you have more than one of the same type ('id' from `tfa status`)", type=str, default=None),
    usage="vastai tfa regen-codes [--code CODE | --backup-code CODE] [--method-type {email,sms,totp}]",
    help="Regenerate backup codes for 2FA",
)
def tfa__regen_codes(args):
    """Regenerate backup codes for 2FA recovery."""
    prompt = "\nThis will invalidate all existing backup codes. Continue? (y|n): "
    if confirm_destructive_action(prompt) == False:
        print("Operation cancelled.")
        return

    client = get_client(args)
    try:
        response_data = auth_api.tfa_regen_codes(
            client, code=args.code, backup_code=args.backup_code,
            method_type=args.method_type, secret=args.secret, method_id=args.method_id,
        )
        if "backup_codes" in response_data:
            save_backup_codes(response_data["backup_codes"])
        else:
            print(f"\n{SUCCESS} Backup codes regenerated successfully!")
            print("(No codes returned in response - this may be an error)")
    except Exception as e:
        if hasattr(e, 'response'):
            handle_failed_tfa_verification(args, e)
        else:
            print(f"Failed to regenerate backup codes: {e}")
        return 1


@parser.command(
    argument("-p", "--phone-number", help="Phone number to receive SMS code (E.164 format, e.g., +1234567890)", type=str, default=None),
    usage="vastai tfa send-sms [--phone-number PHONE_NUMBER]",
    help="Request a 2FA SMS verification code",
    epilog=deindent("""
        Request a two-factor authentication code to be sent via SMS.

        If --phone-number is not provided, uses the phone number on your account.
        The secret token will be returned and must be used with 'vastai tfa activate'.

        Examples:
         vastai tfa send-sms
         vastai tfa send-sms --phone-number +12345678901
    """),
)
def tfa__send_sms(args):
    """Request a 2FA SMS code to be sent to the user's phone."""
    client = get_client(args)
    response_data = auth_api.tfa_send_sms(client, phone_number=args.phone_number)

    secret = response_data.get("secret", "")
    print("SMS code sent successfully!")
    print(f"  Secret token: {secret}")
    print(f"\nOnce you receive the SMS code:")
    phone_num = f"--phone-number {args.phone_number}" if args.phone_number else "[--phone-number <PHONE_NUMBER>]"
    print(f"\n  If you are setting up SMS 2FA for the first time, run:")
    print(f"    vastai tfa activate --sms --secret {secret} {phone_num} [--label <LABEL>] <CODE>")
    print(f"\n  Otherwise you can complete your 2FA log in with:")
    print(f"    vastai tfa login --sms --secret {secret} -c <CODE>\n")


@parser.command(
    usage="vastai tfa send-email",
    help="Request a 2FA Email verification code",
    epilog=deindent("""
        Request a two-factor authentication code to be sent to your email.

        The secret token will be returned and must be used with 'vastai tfa login'.

        Example:
         vastai tfa send-email
    """),
)
def tfa__send_email(args):
    """Request a 2FA email code to be sent to the user's email."""
    client = get_client(args)
    response_data = auth_api.tfa_send_email(client)

    secret = response_data.get("secret", "")
    print(f"{SUCCESS} Email code sent successfully!")
    print(f"  Secret token: {secret}")
    print(f"\nOnce you receive the Email code:")
    print(f"\n  You can complete your 2FA log in with:")
    print(f"    vastai tfa login --secret {secret} -c <CODE>\n")


def print_next_steps_after_new_method_auth():
    print(f"\nNext Steps:"
        "\n To add a new SMS 2FA method:"
        "\n    1. Run `vastai tfa send-sms --phone-number <PHONE_NUMBER>` to receive SMS and get secret token"
        "\n    2. Run `vastai tfa activate --sms --secret <SECRET> --phone-number <PHONE_NUMBER> CODE`\n"
        "\n To add a new TOTP (Authenticator app) 2FA method:"
        "\n    1. Run `vastai tfa totp-setup` to get the manual key/QR code and secret"
        "\n    2. Enter the manual key or scan the QR code with your Authenticator app"
        "\n    3. Run `vastai tfa activate --secret <SECRET> CODE`")


@parser.command(
    argument("-c", "--code", help="2FA code from Authenticator app, SMS, or Email", type=str),
    argument("-s", "--secret", help="Secret token from previous auth step", type=str, default=None),
    argument("-t", "--method-type", mutex_group="type_grp", choices=["email", "sms", "totp"],
             help="2FA Method type. Only use when you only have one method of this type", type=str, default="email"),
    argument("-bc", "--backup-code", mutex_group='type_grp',
             help="One-time backup code (alternative to regular 2FA code)", type=str, default=None),
    argument("-id", "--method-id", mutex_group="type_grp",
             help="2FA Method ID if you have more than one of the same type ('id' from `tfa status`)", type=str, default=None),
    usage="vastai tfa auth-new {[--method-type METHOD_TYPE | --method-id ID | --backup-code BACKUP_CODE] | [--secret SECRET --code CODE]}",
    help="Authorize your account to add a new 2FA method",
    epilog=deindent("""
        Authorize your account to add a new 2FA method by verifying via email or an existing method.

        This is a required step to ensure that only you can add new 2FA methods to your account.

        Step 1. Run command with your chosen verification method:
            - Use '--backup-code BACKUP_CODE' to immediately authorize (skip Step 2)
            - Use --method-type {sms|totp} or --method-id ID to specify which existing method to use
            - Use --method-type email if you have a verified email and/or no other 2FA methods

        Step 2. When prompted, enter the 2FA code to confirm authorization.

        Examples:
         vastai tfa auth-new
         vastai tfa auth-new --method-type totp
         vastai tfa auth-new --backup-code ABCD-EFGH-IJKL
         vastai tfa auth-new --secret abc123def456 --code 123456
    """),
)
def tfa__auth_new(args):
    """Authorize the user to add a new 2FA method by verifying with an existing method."""
    client = get_client(args)

    secret, code = args.secret, args.code
    if not secret and not code:
        try:
            response_data = auth_api.tfa_auth_new(
                client, backup_code=args.backup_code,
                method_type=args.method_type, method_id=args.method_id,
            )
        except Exception as e:
            if hasattr(e, 'response'):
                handle_failed_tfa_verification(args, e)
            else:
                print(f"Authorization failed: {e}")
            return 1

        if args.backup_code and response_data.get("msg") == "Authorization successful.":
            print(f"\n{SUCCESS} Successfully authorized account for adding new 2FA method using backup code")
            print_next_steps_after_new_method_auth()
            return 0

        secret = response_data.get("secret")
        if not secret:
            print(f"\n{FAIL} Error: No secret token received for authorization. Please try again.")
            return 1

        print(f"\n{SUCCESS} Authorization initiated successfully.")
        print(f"2FA Secret: {secret}")
        try:
            code = input("Enter 2FA code to complete authorization: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nOperation cancelled.")
            print("You can still complete this authorization later by running:"
                f"\n  vastai tfa auth-new --secret {secret} --code <CODE>")
            return 1

    try:
        auth_api.tfa_auth_new(client, code=code, secret=secret)
        print(f"\n{SUCCESS} Successfully authorized account for adding new 2FA method!")
        print_next_steps_after_new_method_auth()
    except Exception as e:
        if hasattr(e, 'response'):
            handle_failed_tfa_verification(args, e)
        else:
            print(f"Authorization failed: {e}")
        print(f"\n{FAIL} Authorization failed. Please try again.")
        return 1


@parser.command(
    help="Shows the current 2FA status and configured methods",
    epilog=deindent("""
        Show the current 2FA status for your account, including:
         - Whether or not 2FA is enabled
         - A list of active 2FA methods
         - The number of backup codes remaining (if 2FA is enabled)
    """),
)
def tfa__status(args):
    """Show the current 2FA status for the user."""
    client = get_client(args)
    response_data = auth_api.tfa_status(client)

    if args.raw:
        print(json.dumps(response_data, indent=2))
        return

    tfa_enabled = response_data.get("tfa_enabled", False)
    methods = response_data.get("methods", [])
    backup_codes_remaining = response_data.get("backup_codes_remaining", 0)

    if not tfa_enabled or not methods:
        print(f"{WARN}  No active 2FA methods found")
    else:
        print(f"2FA Status: Enabled {SUCCESS}")
        print(f"\nActive 2FA Methods:")
        display_tfa_methods(methods)
        print(f"\nBackup codes remaining: {backup_codes_remaining}")


@parser.command(
    usage="vastai tfa totp-setup",
    help="Generate TOTP secret and QR code for Authenticator app setup",
    epilog=deindent("""
        Set up TOTP (Time-based One-Time Password) 2FA using an Authenticator app.

        This command generates a new TOTP secret and displays:
        - A QR code (for scanning with your app)
        - A manual entry key (for typing into your app)
        - A secret token (needed for the next step)

        Workflow:
         1. Run this command to generate the TOTP secret
         2. Add the account to your Authenticator app by either:
            - Scanning the displayed QR code, OR
            - Manually entering the key shown
         3. Once added, your app will display a 6-digit code
         4. Complete setup by running:
            vastai tfa activate --secret <SECRET> <CODE>

        Supported Authenticator Apps:
         - Google Authenticator
         - Microsoft Authenticator
         - Authy
         - 1Password
         - Any TOTP-compatible app

        Example:
         vastai tfa totp-setup
    """),
)
def tfa__totp_setup(args):
    """Generate a TOTP secret and QR code for setting up Authenticator app 2FA."""
    client = get_client(args)
    response_data = auth_api.tfa_totp_setup(client)

    if args.raw:
        print(json.dumps(response_data, indent=2))
        return

    secret = response_data.get("secret", "")
    provisioning_uri = response_data.get("provisioning_uri", "")

    print("\n" + "=" * 60)
    print("TOTP (Authenticator App) 2FA Setup")
    print("=" * 60)

    print("\nScan this QR code with your Authenticator app:\n")

    try:
        import qrcode
        qr = qrcode.QRCode(border=2)
        qr.add_data(provisioning_uri)
        qr.make()
        qr.print_ascii(tty=True)
    except ImportError:
        print("  [QR code display requires 'qrcode' package]")
        print(f"  Install with: pip install qrcode")
        print(f"\n  Or manually enter this URI in your app:")
        print(f"  {provisioning_uri}")

    print("\nOR Manual Entry Key (type this into your Authenticator app):")
    print(f"  {secret}")

    print("\nNext Steps:")
    print("  1. Your Authenticator app should now display a 6-digit code")
    print("  2. Complete setup by running:")
    print(f"     vastai tfa activate --secret {secret} <CODE>")
    print("\n" + "=" * 60 + "\n")


@parser.command(
    argument("method_id", metavar="METHOD_ID", help="ID of the 2FA method to update (see `vastai tfa status`)", type=int),
    argument("-l", "--label", help="New label/name for this 2FA method", type=str, default=None),
    argument("-p", "--set-primary", help="Set this method as the primary/default 2FA method", default=None),
    usage="vastai tfa update METHOD_ID [--label LABEL] [--set-primary]",
    help="Update a 2FA method's settings",
    epilog=deindent("""
        Update the label or primary status of a 2FA method.

        The label is a friendly name to help you identify different methods
        (e.g. "Work Phone", "Personal Authenticator").

        The primary method is your preferred/default 2FA method.

        Examples:
         vastai tfa update 123 --label "Work Phone"
         vastai tfa update 456 --set-primary
         vastai tfa update 789 --label "Backup Authenticator" --set-primary
    """),
)
def tfa__update(args):
    """Update settings for an existing 2FA method."""
    label = args.label
    set_primary = args.set_primary

    if set_primary is not None:
        if set_primary.lower() in {'true', 't'}:
            set_primary = True
        elif set_primary.lower() in {'false', 'f'}:
            set_primary = False
        else:
            print("Error: --set-primary must be <t|true> or <f|false>")
            return

    if label is None and set_primary is None:
        print("Error: You must specify at least one field to update (--label or --set-primary)")
        return 1

    client = get_client(args)
    try:
        response_data = auth_api.tfa_update(client, method_id=args.method_id, label=label, set_primary=set_primary)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    if args.raw:
        return response_data

    print("\n2FA method updated successfully!")
    if args.label:
        print(f"   New label: {args.label}")
    if set_primary is not None:
        print(f"   Set as primary method = {set_primary}")
