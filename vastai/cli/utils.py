"""Shared helpers used across all CLI command modules."""


def get_parser():
    from vastai.cli.main import parser
    return parser


def get_client(args):
    """Create a VastClient from parsed CLI args."""
    from vastai.api.client import VastClient
    return VastClient(
        api_key=args.api_key,
        server_url=args.url,
        retry=args.retry,
        explain=getattr(args, 'explain', False),
        curl=getattr(args, 'curl', False),
    )
