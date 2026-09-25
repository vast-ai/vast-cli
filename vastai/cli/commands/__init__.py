"""CLI command modules.

Each module registers its commands with the global parser at import time
via the ``@parser.command(...)`` decorator pattern.  Importing a module
is sufficient to register all of its commands.
"""


def register_all_commands(parser):
    """Import all command modules to register their commands with the parser.

    The imports themselves trigger the decorator registrations -- no
    explicit ``register()`` call is needed per module.

    This is the single list of enabled command modules: ``main()`` and the
    docs generator (scripts/generate_cli_sdk_docs.py) both call it. When they
    kept separate lists, ``repl``, ``update`` and ``uninstall`` were live in
    the CLI but missing here, so they never got a docs page.
    """
    from vastai.cli.commands import (  # noqa: F401
        instances, offers, machines, teams, keys, endpoints,
        billing, storage, auth, misc, deployments, metrics,
        benchmarks,
        price_increase,
        repl,
        update,
        uninstall,
        # clusters,  # cluster/overlay commands disabled for now
    )
