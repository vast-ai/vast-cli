"""CLI command modules.

Each module registers its commands with the global parser at import time
via the ``@parser.command(...)`` decorator pattern.  Importing a module
is sufficient to register all of its commands.
"""


def register_all_commands(parser):
    """Import all command modules to register their commands with the parser.

    The imports themselves trigger the decorator registrations -- no
    explicit ``register()`` call is needed per module.
    """
    from vastai.cli.commands import (  # noqa: F401
        instances, offers, machines, teams, keys, endpoints,
        billing, storage, auth, misc,
        # clusters,  # cluster/overlay commands disabled for now
    )
