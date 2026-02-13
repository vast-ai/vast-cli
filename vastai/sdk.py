"""
Vast.ai Python SDK.

This module provides the VastAI class, a Python SDK client for the Vast.ai GPU
cloud platform. It wraps the vast.py CLI commands and exposes them as Python
methods with proper type hints and docstrings.

Example:
    Basic usage::

        from vastai import VastAI

        client = VastAI(api_key="your-api-key")
        offers = client.search_offers(limit=10)
        print(f"Found {len(offers)} offers")

    Creating an instance::

        offer_id = offers[0]["id"]
        result = client.create_instance(id=offer_id, image="pytorch/pytorch:latest")

    Checking instances::

        instances = client.show_instances()
        for inst in instances:
            print(f"ID: {inst['id']}, Status: {inst['actual_status']}")

The SDK automatically handles authentication, retries, and output capture.
All methods return parsed JSON when ``raw=True`` (the default for SDK usage).
"""

import types
import argparse
from typing import Any, Callable
import io
import inspect
import re
import os
import sys
import logging
from pyparsing import Word, alphas, alphanums, oneOf, Group, ZeroOrMore, quotedString, delimitedList, Suppress

from .vastai_base import VastAIBase
from vast import parser, APIKEY_FILE
import vast as _vast
from textwrap import dedent

#ogging.basicConfig(level=os.getenv('LOGLEVEL') or logging.INFO)
logger = logging.getLogger()


_regions = {
  'AF': ('DZ,AO,BJ,BW,BF,BI,CM,CV,CF,TD,KM,CD,CG,DJ,EG,GQ,ER,ET,GA,GM,GH,GN,'
         'GW,KE,LS,LR,LY,MW,MA,ML,MR,MU,MZ,NA,NE,NG,RW,SH,ST,SN,SC,SL,SO,ZA,'
         'SS,SD,SZ,TZ,TG,TN,UG,YE,ZM,ZW'),  # Africa
  'AS': ('AE,AM,AR,AU,AZ,BD,BH,BN,BT,MM,KH,KW,KP,IN,ID,IR,IQ,IL,JP,JO,KZ,LV,'
         'LI,MY,MV,MN,NP,KR,PK,PH,QA,SA,SG,LK,SY,TW,TJ,TH,TR,TM,VN,YE,HK,'
         'CN,OM'),  # Asia
  'EU': ('AL,AD,AT,BY,BE,BA,BG,HR,CY,CZ,DK,EE,'
         'FI,FR,GE,DE,GR,HU,IS,IT,KZ,LV,LI,LT,'
         'LU,MT,MD,MC,ME,NL,NO,PL,PT,RO,RU,RS,'
         'SK,SI,ES,SE,CH,UA,GB,VA,MK'),  # Europe
  'LC': ('AG,AR,BS,BB,BZ,BO,BR,CL,CO,CR,CU,DO,EC,SV,GY,HT,HN,JM,MX,NI,PA,PY,'
         'PE,PR,RD,SUR,TT,UR,VZ'),  # Latin America and the Caribbean
  'NA': 'CA,US',  # Northern America
  'OC': ('AU,FJ,GU,KI,MH,FM,NR,NZ,PG,PW,SL,TO,TV,VU'),  # Oceania
}

def reverse_mapping(regions: dict[str, str]) -> dict[str, str]:
    """
    Create a reverse mapping from country codes to region codes.

    Args:
        regions: Dict mapping region codes (e.g., 'NA', 'EU') to comma-separated
            country codes (e.g., 'CA,US').

    Returns:
        Dict mapping each country code to its region code.

    Example:
        >>> regions = {'NA': 'CA,US', 'EU': 'DE,FR'}
        >>> reverse_mapping(regions)
        {'CA': 'NA', 'US': 'NA', 'DE': 'EU', 'FR': 'EU'}
    """
    reversed_mapping: dict[str, str] = {}
    for region, countries in regions.items():
        for country in countries.split(','):
            reversed_mapping[country] = region
    return reversed_mapping

_regions_rev = reverse_mapping(_regions)


def queryParser(kwargs: dict[str, Any], instance: "VastAI") -> tuple[dict[str, bool], dict[str, Any]]:
    """
    Pre-process query parameters before API call.

    Parses the query string to extract state flags (georegion, chunked) and
    transforms geolocation queries when georegion mode is enabled.

    Args:
        kwargs: Keyword arguments passed to the SDK method, including 'query'.
        instance: The VastAI instance for context.

    Returns:
        A tuple of (state_dict, modified_kwargs) where:
            - state_dict contains boolean flags for 'georegion' and 'chunked'
            - modified_kwargs has the transformed query string

    Note:
        - 'georegion=true' in query enables region-based geolocation expansion
        - 'chunked=true' enables value chunking for SkyPilot compatibility
    """
    # georegion uses the region modifiers as top level
    # descriptors
    #
    # chunked reduces values communicated to more usable chunks
    state: dict[str, bool] = {'georegion': False, 'chunked': False }

    if kwargs.get('query') is not None:
        qstr = kwargs['query']

        key = Word(alphas + "_-")
        operator = oneOf("= in != > < >= <=")
        single_value = Word(alphanums + "_.-") | quotedString

        array_value = (
            Suppress("[") + delimitedList(quotedString) + Suppress("]")
        ).setParseAction(lambda t: f"[{','.join(t)}]")
        value = single_value | array_value
        expr = Group(key + operator + value)
        query = ZeroOrMore(expr)
        parsed = query.parseString(qstr)

        toPass = []

        for state_key in state.keys():
            state[state_key] = any([state_key, '=', 'true'] == list(expr) for expr in parsed)

        for expr in parsed:
            if expr[0] in state.keys():
                continue

            elif expr[0] == 'geolocation' and state['georegion']:
                region = _regions.get(str(expr[2]).strip('"'))
                expr_list: list[str] = ['geolocation', 'in', f'[{region}]']
                toPass.append(' '.join(expr_list))
                continue

            toPass.append(' '.join(str(e) for e in expr))

        kwargs['query'] = ' '.join(toPass)

    return (state, kwargs)

def queryFormatter(state: dict[str, bool], obj: list[dict[str, Any]], instance: "VastAI") -> list[dict[str, Any]]:
    """
    Post-process search results based on query state flags.

    Transforms search results by:
    - Adding 'datacenter' boolean field
    - Expanding geolocation to include region code when georegion=true
    - Filtering and chunking values when chunked=true (for SkyPilot)

    Args:
        state: State dict from queryParser with 'georegion' and 'chunked' flags.
        obj: List of offer dictionaries from the API response.
        instance: The VastAI instance for context.

    Returns:
        Filtered and transformed list of offer dictionaries.

    Note:
        This algorithm is designed for SkyPilot integration to provide
        standardized catalog offerings with chunked resource values.
    """
    # This algo is explicitly designed for skypilot to add
    # depth to our catalog offerings
    cutoff: dict[str, int] = {
        'cpu_ram': 64 * 1024,
        'cpu_cores': 32,
        'min_bid': 0
    }

    filtered: list[dict[str, Any]] = []
    for res in obj:
        res['datacenter'] = (res['hosting_type'] == 1)
        if state['georegion'] and res['geolocation'] is not None:
            country = res['geolocation'][-2:]
            res['geolocation'] += f', {_regions_rev[country]}'

        if state['chunked']:
            good = True

            try:
                for k, v in cutoff.items():
                    if res[k] is not None and (res[k] < cutoff[k]):
                        good = False
                    else:
                        res[k] = cutoff[k]
            except (KeyError, TypeError):
                good = False

            if not good:
                continue

            #res['cpu_ram'] = upper(res['cpu_ram'])
            #res['cpu_cores'] = max(res['cpu_cores'] & 0xffff8, 4)
            res['gpu_ram'] = res['gpu_ram'] & 0xffffffffff0
            res['disk_space'] = int(res['disk_space']) & 0xffffffffffc0

        filtered.append(res)

    return filtered

def lastOutput(state: dict[str, bool] | None, obj: Any, instance: "VastAI") -> str | None:
    """
    Return captured stdout output from the last command.

    Used as a post-hook for commands like 'logs' and 'execute' where the
    important output is printed to stdout rather than returned.

    Args:
        state: State dict (unused, for hook signature compatibility).
        obj: Return value from the CLI function (unused).
        instance: The VastAI instance containing last_output.

    Returns:
        The captured stdout content from the last command execution.
    """
    return instance.last_output

# Hook functions: [pre_hook, post_hook] for each command
# Pre-hooks transform kwargs, post-hooks transform results
_hooks: dict[str, list[Callable[..., Any] | None]] = {
    'search__offers': [queryParser, queryFormatter],
    'logs': [None, lastOutput],
    'execute': [None, lastOutput]
}

class VastAI(VastAIBase):
    """
    Python SDK client for the Vast.ai GPU cloud platform.

    VastAI provides programmatic access to all Vast.ai CLI commands through
    a clean Python interface. Each CLI command maps to a method on this class,
    with 130+ methods covering instances, offers, billing, teams, and more.

    Example:
        Basic usage::

            >>> from vastai import VastAI
            >>> client = VastAI(api_key="your-api-key")
            >>> offers = client.search_offers()
            >>> print(offers[:3])  # First 3 offers

        Creating an instance::

            >>> offer_id = offers[0]["id"]
            >>> result = client.create_instance(id=offer_id, image="pytorch/pytorch:latest")
            >>> print(result)

        Checking instances::

            >>> instances = client.show_instances()
            >>> for inst in instances:
            ...     print(f"ID: {inst['id']}, Status: {inst['actual_status']}")

    Attributes:
        api_key: The Vast.ai API key for authentication.
        raw: If True, methods return raw JSON dicts. If False, output is printed.
        retry: Number of retry attempts for failed requests (default: 3).
        server_url: Base URL for the Vast.ai API (default: https://console.vast.ai).
        explain: If True, print API endpoint details before requests.
        quiet: If True, suppress non-essential output.
        curl: If True, print equivalent curl commands.
        creds_source: Read-only property indicating API key source ('CODE', 'FILE', 'NONE').

    Note:
        Methods that return lists (search_*, show_*s) return ``list[dict[str, Any]]``.
        Methods that return single objects return ``dict[str, Any]``.
        Check method docstrings for specific return types.

    See Also:
        - :doc:`/sdk/quickstart` for a step-by-step guide
        - :doc:`/sdk/reference/vastai` for full API reference
    """

    def __init__(
        self,
        api_key: str | None = None,
        server_url: str = "https://console.vast.ai",
        retry: int = 3,
        raw: bool = True,
        explain: bool = False,
        quiet: bool = False,
        curl: bool = False,
    ) -> None:
        """
        Initialize a VastAI client.

        Args:
            api_key: Vast.ai API key. If not provided, reads from environment
                variable VAST_API_KEY or ~/.config/vastai/vast_api_key file.
            server_url: Base URL for the Vast.ai API. Override for testing or
                alternate endpoints. Defaults to "https://console.vast.ai".
            retry: Number of retry attempts for transient failures (429, 5xx errors).
                Defaults to 3.
            raw: If True, methods return parsed JSON. If False, output is printed
                to stdout (CLI behavior). Defaults to True for SDK usage.
            explain: If True, print HTTP method and URL before each request.
                Useful for debugging. Defaults to False.
            quiet: If True, suppress progress messages and other non-essential
                output. Defaults to False.
            curl: If True, print equivalent curl commands for each API call.
                Useful for debugging. Defaults to False.

        Raises:
            ValueError: If api_key is not provided and cannot be found in
                environment or config file (raised by some methods, not __init__).

        Example:
            Basic initialization::

                >>> client = VastAI(api_key="your-key")

            With custom options::

                >>> client = VastAI(
                ...     api_key="your-key",
                ...     retry=5,
                ...     explain=True,
                ...     quiet=True
                ... )

            Using stored credentials::

                >>> # After running: vastai set api-key YOUR_KEY
                >>> client = VastAI()  # Reads from config file
        """
        # Instance attribute type declarations
        self._creds: str
        self._KEYPATH: str
        self.api_key: str | None
        self.api_key_access: str | None
        self.server_url: str
        self.retry: int
        self.raw: bool
        self.explain: bool
        self.quiet: bool
        self.curl: bool
        self.imported_methods: dict[str, dict[str, Any]]
        self.last_output: str | None

        if not api_key:
            if os.path.exists(APIKEY_FILE):
                with open(APIKEY_FILE, "r") as reader:
                    api_key = reader.read().strip()
                    self._creds = "FILE"
            else:
                self._creds = "NONE"
        else:
            self._creds = "CODE"

        self._KEYPATH = APIKEY_FILE
        self.api_key = api_key
        self.api_key_access = api_key
        self.server_url = server_url
        self.retry = retry
        self.raw = raw
        self.explain = explain
        self.quiet = quiet
        self.curl = curl
        self.imported_methods = {}
        self.last_output = None
        self.import_cli_functions()

    @property
    def creds_source(self) -> str:
        """
        Return the source of the API key credentials.

        Returns:
            One of:
                - 'CODE': API key was passed to constructor
                - 'FILE': API key was read from config file
                - 'NONE': No API key found
        """
        return self._creds

    def generate_signature_from_argparse(
        self, parser: argparse.ArgumentParser
    ) -> tuple[inspect.Signature, str]:
        """
        Generate a Python function signature from an argparse ArgumentParser.

        Introspects the parser's actions to build an inspect.Signature and
        corresponding docstring Args section for the wrapped method.

        Args:
            parser: The argparse.ArgumentParser for a CLI subcommand.

        Returns:
            A tuple of (Signature, docstring) where:
                - Signature is an inspect.Signature with typed parameters
                - docstring is a Google-style Args section string
        """
        parameters: list[inspect.Parameter] = [inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD)]
        isFirst: bool = True
        docstring: str = ''

        for action in sorted(parser._actions,  key=lambda action: len(action.option_strings) > 0):
            if action.dest == 'help':
                continue
            if action.help and "Alias" in action.help:
                continue

            # Determine parameter kind
            kind: inspect._ParameterKind = inspect.Parameter.POSITIONAL_OR_KEYWORD
            if action.option_strings:
                kind = inspect.Parameter.KEYWORD_ONLY

            # Determine default and annotation
            default = action.default if action.default != argparse.SUPPRESS else None
            annotation = action.type if action.type else Any

            # Create the parameter
            param = inspect.Parameter(
                action.dest,
                kind=kind,
                default=default,
                annotation=annotation
            )
            parameters.append(param)

            if isFirst:
                docstring = 'Args:\n'
                isFirst = False

            param_type = annotation.__name__ if hasattr(annotation, "__name__") else "Any"
            help_text = f"{action.help or 'No description'}"
            docstring += f"\t{action.dest} ({param_type}): {help_text}\n"
            if default is not None:
                docstring += f"\t\tDefault is {default}.\n"

        # Return a custom Signature object
        sig = inspect.Signature(parameters)
        return sig, docstring

    def import_cli_functions(self) -> None:
        """
        Dynamically import functions from vast.py and bind them as instance methods.

        Iterates through all subparsers in the CLI argument parser and creates
        wrapper methods for each command. The wrapper handles argument validation,
        stdout capture, and hook execution.

        This is called automatically during __init__ and populates the
        imported_methods dict with argument metadata for each command.
        """
        if hasattr(parser, "subparsers_") and parser.subparsers_:
            for name, subparser in parser.subparsers_.choices.items():
                if name == "help":
                    continue
                if hasattr(subparser, "default") and callable(subparser.default):
                    func = subparser.default
                elif hasattr(subparser, "_defaults") and "func" in subparser._defaults:
                    func = subparser._defaults["func"]
                else:
                    print(
                        f"Command {subparser.prog} does not have an associated function."
                    )
                    continue

                func_name = func.__name__.replace("__", "_")
                wrapped_func = self.create_wrapper(func, func_name)
                setattr(self, func_name, types.MethodType(wrapped_func, self))
                arg_details = {}
                if hasattr(subparser, "_actions"):
                    for action in subparser._actions:
                        if action.dest != "help" and hasattr(action, "option_strings"):
                            arg_details[action.dest] = {
                                "option_strings": action.option_strings,
                                "help": action.help,
                                "default": action.default,
                                "type": str(action.type) if action.type else None,
                                "required": action.default is None and action.required,
                                "choices": getattr(
                                    action, "choices", None
                                ),  # Capture choices
                            }

                #globals()[func_name] = arg_details
                self.imported_methods[func_name] = arg_details
        else:
            print("No subparsers have been configured.")

    def create_wrapper(
        self, func: Callable[..., Any], method_name: str
    ) -> Callable[..., Any]:
        """
        Create a wrapper function for a CLI command.

        The wrapper handles:
        - Required argument validation
        - Choice validation for enum-like arguments
        - Default value injection from argparse
        - SDK-level defaults (api_key, server_url, etc.)
        - Pre/post hooks for query transformation
        - Stdout capture in raw mode
        - SystemExit handling for CLI functions

        Args:
            func: The CLI function to wrap (e.g., search__offers).
            method_name: The SDK method name (e.g., 'search_offers').

        Returns:
            A wrapper function that can be bound as an instance method.
        """

        def wrapper(self: "VastAI", **kwargs: Any) -> Any:
            arg_details = self.imported_methods.get(method_name, {})
            for arg, details in arg_details.items():
                if details["required"] and arg not in kwargs:
                    raise ValueError(f"Missing required argument: {arg}")
                if (
                    arg in kwargs
                    and details.get("choices") is not None
                    and kwargs[arg] not in details["choices"]
                ):
                    raise ValueError(
                        f"Invalid choice for {arg}: {kwargs[arg]}. Valid options are {details['choices']}"
                    )
                kwargs.setdefault(arg, details["default"])

            kwargs.setdefault("api_key", self.api_key)
            kwargs.setdefault("url", self.server_url)
            kwargs.setdefault("retry", self.retry)
            kwargs.setdefault("raw", self.raw)
            kwargs.setdefault("explain", self.explain)
            kwargs.setdefault("quiet", self.quiet)
            kwargs.setdefault("curl", self.curl)

            # if we specified hooks we get that now
            state: dict[str, bool] | None = None
            hooks_list = _hooks.get(func.__name__)
            if hooks_list is not None:
              pre_hook = hooks_list[0]
              if pre_hook is not None:
                state, kwargs = pre_hook(kwargs, self)

            namespace_args: argparse.Namespace = argparse.Namespace(**kwargs)
            _vast.ARGS = namespace_args  # type: ignore[assignment]

            if logger.isEnabledFor(logging.DEBUG):
                kwargs_repr = {key: repr(value) for key, value in kwargs.items()}
                logging.debug(f"Calling {func.__name__} with arguments: kwargs={kwargs_repr}")

            # Setup stdout capture with proper cleanup via finally block
            out_b = None
            out_o = None
            if not logger.isEnabledFor(logging.DEBUG):
                out_b = io.StringIO()
                out_o = sys.stdout
                sys.stdout = out_b

            res: Any = None
            try:
                res = func(namespace_args)
            except SystemExit as e:
                # CLI functions call sys.exit(); capture exit code as return value
                if e.code is not None and e.code != 0:
                    logging.warning(f"CLI function {func.__name__} exited with code {e.code}")
                res = e.code
            except Exception as e:
                logging.warning(f"Error calling {func.__name__}: {e}")
                res = None
            finally:
                # ALWAYS restore stdout, even if unexpected exceptions occur
                if out_o is not None:
                    sys.stdout = out_o
                if out_b is not None:
                    try:
                        self.last_output = out_b.getvalue()
                    finally:
                        out_b.close()

            hooks_list_post = _hooks.get(func.__name__)
            if hooks_list_post is not None:
              post_hook = hooks_list_post[1]
              if post_hook is not None:
                res = post_hook(state, res, self)

            if hasattr(res, 'json'):
               logging.debug(f" └-> {res.json()}")
               return res.json()

            logging.debug(f" └-> {res}")

            return res

        func_name = func.__name__.replace("__", "_")
        wrapper.__name__ = func_name

        wrapper.__doc__ = ''
        hasDoc = False
        # We don't want to be redundant so we look for help in various places and
        # if it's not empty after we parse through it then we use it as our
        # canonical help. So we go in this order:
        #
        #   func.__doc__
        #   sig.epilog
        #   sig.help
        #

        if func.__doc__:
            doc = dedent(re.sub(r'\s(:param|@).*', '', func.__doc__, flags=re.DOTALL)).strip()
            if doc:
               hasDoc = True
               wrapper.__doc__ += f"{doc}\n\n"

        sig = getattr(func, "mysignature", None)
        sig_help = getattr(func, "mysignature_help", None)

        if sig:
            wrapper.__signature__, docappend = self.generate_signature_from_argparse(sig)  # type: ignore[attr-defined]

            # append epilog if exists
            if getattr(sig, "epilog", None):
                wrapper.__doc__ = f"{wrapper.__doc__.rstrip()}\n\n{sig.epilog.strip()}\n"

            # if no epilog or func docstring, fall back to parser help text
            elif sig_help and not hasDoc:
                wrapper.__doc__ += f"\n\n{sig_help}"

            # finally append the arg details
            wrapper.__doc__ = f"{wrapper.__doc__.rstrip()}\n\n{docappend}"

        return wrapper

    def credentials_on_disk(self) -> None:
        """
        No-operation method for credential validation.

        This method exists to ensure library compatibility and verify that
        API key file handling doesn't cause crashes. It performs no action.

        Note:
            This is a stub method that may be overridden by subclasses
            for actual credential validation.
        """
        pass

    def __getattr__(self, name: str) -> Any:
        """
        Handle attribute access for dynamically imported methods.

        Provides a fallback for attribute lookup that checks imported_methods
        before raising AttributeError.

        Args:
            name: The attribute name being accessed.

        Returns:
            The requested attribute if found in imported_methods.

        Raises:
            AttributeError: If the attribute is not found.
        """
        if name in self.imported_methods:
            return getattr(self, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name}")
