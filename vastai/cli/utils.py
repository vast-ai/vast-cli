"""Shared helpers used across all CLI command modules."""


def get_parser():
    from vastai.cli.main import parser
    return parser


def get_client(args):
    """Create a VastClient from parsed CLI args."""
    from vastai.api.client import VastClient
    from vastai.cli.util import ensure_host_role_detected
    client = VastClient(
        api_key=args.api_key,
        server_url=args.url,
        retry=args.retry,
        explain=getattr(args, 'explain', False),
        curl=getattr(args, 'curl', False),
        client_type="cli",
    )
    # Lazily resolves the client/host CLI role for a pre-existing install that predates this feature (CLN-3582).
    ensure_host_role_detected(client)
    return client
