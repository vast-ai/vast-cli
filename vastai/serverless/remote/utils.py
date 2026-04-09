from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import os
import re
import tarfile
import tempfile
from typing import TYPE_CHECKING, Tuple, BinaryIO

if TYPE_CHECKING:
    from vastai.serverless.remote.base import Config


def _sanitize_info(
    info: tarfile.TarInfo, arcname: str | None = None
) -> tarfile.TarInfo:
    """Set uid/gid to 0 on a TarInfo.

    If arcname is provided, override info.name. This is needed because
    gettarinfo strips leading '/' from absolute arcnames.
    """
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    if arcname is not None:
        info.name = arcname
    return info


def add_file(tf: tarfile.TarFile, src_path: str, arcname: str) -> None:
    """Add a single file to the tarball under arcname, with uid/gid 0."""
    info = tf.gettarinfo(src_path, arcname=arcname)
    _sanitize_info(info, arcname)
    with open(src_path, "rb") as f:
        tf.addfile(info, f)


def add_folder(tf: tarfile.TarFile, src_path: str, arcname: str) -> None:
    """Recursively add a folder to the tarball, renaming the root to arcname, with uid/gid 0."""
    src_path = os.path.normpath(src_path)
    for root, dirs, files in os.walk(src_path):
        rel = os.path.relpath(root, src_path)
        arc_root = arcname if rel == "." else os.path.join(arcname, rel)

        # Add directory entry
        info = tf.gettarinfo(root, arcname=arc_root)
        _sanitize_info(info, arc_root)
        tf.addfile(info)

        for fname in files:
            file_path = os.path.join(root, fname)
            arc_path = os.path.join(arc_root, fname)
            info = tf.gettarinfo(file_path, arcname=arc_path)
            _sanitize_info(info, arc_path)
            with open(file_path, "rb") as f:
                tf.addfile(info, f)


def add_string(
    tf: tarfile.TarFile,
    content: str,
    arcname: str,
    executable: bool = False,
) -> None:
    """Add a string as a text file to the tarball with uid/gid 0.

    If executable=True, the file gets mode 0o755; otherwise 0o644.
    """
    data = content.encode("utf-8")
    info = tarfile.TarInfo(name=arcname)
    info.size = len(data)
    info.mode = 0o755 if executable else 0o644
    _sanitize_info(info)
    tf.addfile(info, io.BytesIO(data))


def add_path(tf: tarfile.TarFile, src_path: str, arcname: str) -> None:
    """Add a file or directory to the tarball, dispatching to add_file or add_folder."""
    if os.path.isdir(src_path):
        add_folder(tf, src_path, arcname)
    elif os.path.isfile(src_path):
        add_file(tf, src_path, arcname)
    else:
        raise FileNotFoundError(f"Source path does not exist: {src_path}")


def serialize_config(config: Config) -> str:
    """JSON-serialize a Config dataclass."""
    return json.dumps(dataclasses.asdict(config))


def is_python_package(path: str) -> bool:
    """Return True if path is a Python package directory (contains __init__.py)."""
    return os.path.isdir(path) and os.path.isfile(os.path.join(path, "__init__.py"))


def is_python_module(path: str) -> bool:
    """Return True if path is a single .py file."""
    return os.path.isfile(path) and path.endswith(".py")


def deployment_arcname(deployment_path: str) -> str:
    """Return the archive name for a deployment: './deployment' for packages, './deployment.py' for modules.

    Raises ValueError if the path is neither a Python package nor a module.
    """
    if is_python_package(deployment_path):
        return "./deployment"
    if is_python_module(deployment_path):
        return "./deployment.py"
    raise ValueError(
        f"Deployment path is neither a Python package (directory with __init__.py) "
        f"nor a Python module (.py file): {deployment_path}"
    )


IGNORE_COMMENT_BODY = b"!VAST_IGNORE_CHANGES"

# Matches the closing delimiter (with escape handling) for a multiline string.
_CLOSE_MULTILINE_RE = {
    b'"""': re.compile(rb'(?:[^\\]|\\.)*?"""'),
    b"'''": re.compile(rb"(?:[^\\]|\\.)*?'''"),
}

# Tokenizer for Python source outside multiline strings.
# Matches (in priority order): closed triple-quoted strings, unclosed
# triple-quotes (groups 1/2), single-quoted strings, or comment start (group 3).
# Unclosed triple-quotes MUST precede single-quote patterns, otherwise
# "..." would consume "" from the start of """.
# Unmatched text (code, whitespace, etc.) is simply skipped by finditer.
_PYTHON_TOKEN_RE = re.compile(
    rb'"""(?:[^\\]|\\.)*?"""|'
    rb"'''(?:[^\\]|\\.)*?'''|"
    rb'(""")|'
    rb"(''')|"
    rb'"(?:[^"\\\n]|\\.)*"|'
    rb"'(?:[^'\\\n]|\\.)*'|"
    rb"(#)"
)


def _scan_python_line(
    line: bytes,
    in_multiline: bytes | None,
) -> tuple[bool, bytes | None]:
    """Scan a Python source line left-to-right, tracking string context.

    Returns (has_ignore_comment, new_multiline_state).
    """
    i = 0
    if in_multiline is not None:
        m = _CLOSE_MULTILINE_RE[in_multiline].match(line)
        if m is None:
            return False, in_multiline
        i = m.end()

    for m in _PYTHON_TOKEN_RE.finditer(line, i):
        if m.group(1):
            return False, b'"""'
        if m.group(2):
            return False, b"'''"
        if m.group(3):
            comment_body = line[m.start() + 1 :].strip()
            return comment_body == IGNORE_COMMENT_BODY, None

    return False, None


def filter_ignored_lines(data: bytes) -> bytes:
    """Remove lines whose comment is exactly ``#!VAST_IGNORE_CHANGES``.

    Tracks triple-quoted multiline strings so that occurrences inside string
    literals are not treated as comments.
    """
    lines = data.split(b"\n")
    result: list[bytes] = []
    in_multiline: bytes | None = None
    for line in lines:
        has_ignore, in_multiline = _scan_python_line(line, in_multiline)
        if not has_ignore:
            result.append(line)
    return b"\n".join(result)


def read_file_for_hash(path: str, filter_comments: bool = False) -> bytes:
    """Read a file's bytes for hashing.

    When filter_comments is True and the file is a .py file, lines whose
    comment is exactly ``# !VAST_IGNORE_CHANGES`` are excluded.
    """
    with open(path, "rb") as f:
        data = f.read()
    if filter_comments and path.endswith(".py"):
        data = filter_ignored_lines(data)
    return data


def hash_update_file(
    hasher: hashlib._Hash,
    src_path: str,
    arcname: str,
    filter_comments: bool = False,
) -> None:
    """Feed a single file into the hasher: its archive name followed by its content."""
    hasher.update(arcname.encode("utf-8"))
    hasher.update(read_file_for_hash(src_path, filter_comments=filter_comments))


def hash_update_directory(
    hasher: hashlib._Hash,
    src_path: str,
    arcname: str,
    filter_comments: bool = False,
) -> None:
    """Walk a directory in sorted order, feeding each file into the hasher."""
    src_path = os.path.normpath(src_path)
    for root, dirs, files in os.walk(src_path):
        dirs.sort()
        rel = os.path.relpath(root, src_path)
        arc_root = arcname if rel == "." else os.path.join(arcname, rel)
        for fname in sorted(files):
            hash_update_file(
                hasher,
                os.path.join(root, fname),
                os.path.join(arc_root, fname),
                filter_comments=filter_comments,
            )


def hash_update_path(
    hasher: hashlib._Hash,
    src_path: str,
    arcname: str,
    filter_comments: bool = False,
) -> None:
    """Feed a file or directory into the hasher, dispatching appropriately."""
    if os.path.isdir(src_path):
        hash_update_directory(
            hasher, src_path, arcname, filter_comments=filter_comments
        )
    elif os.path.isfile(src_path):
        hash_update_file(hasher, src_path, arcname, filter_comments=filter_comments)
    else:
        raise FileNotFoundError(f"Source path does not exist: {src_path}")


def compute_deployment_hash(
    config: Config,
    deployment_path: str,
    extra_files: list[tuple[str, str]] | None = None,
) -> str:
    """Compute a SHA-256 hex digest over deployment data without creating a tarball.

    Hashes (in order):
      1. The JSON-serialized Config
      2. The deployment files (with #!VAST_IGNORE_CHANGES comment lines excluded from .py files)
      3. Any extra files (no comment filtering)

    Args:
        config: The deployment Config object.
        deployment_path: Path to the deployment source (a .py file or a package directory).
        extra_files: List of (source_path, dest_path) pairs.
    """
    hasher = hashlib.sha256()
    hasher.update(serialize_config(config).encode("utf-8"))
    hash_update_path(
        hasher,
        deployment_path,
        deployment_arcname(deployment_path),
        filter_comments=True,
    )
    for src, dest in extra_files or []:
        hash_update_path(hasher, src, dest)
    return hasher.hexdigest()


def create_deployment_tarball(
    tar_path: str,
    config: Config,
    deployment_path: str,
    extra_files: list[tuple[str, str]] | None = None
):
    """Create a deployment tarball in /tmp and return its path.

    The tarball contains:
      - ./config.json        — JSON-serialized Config
      - ./deployment[.py]    — the deployment package or module
      - extra files at their specified destination paths

    Args:
        config: The deployment Config object.
        deployment_path: Path to the deployment source (a .py file or a package directory).
        extra_files: List of (source_path, dest_path) pairs. dest_path may be absolute.
    """
    tf = tarfile.TarFile.open(tar_path, mode="w:gz")
    try:
        add_string(tf, serialize_config(config), "./config.json")
        add_path(tf, deployment_path, deployment_arcname(deployment_path))
        for src, dest in extra_files or []:
            add_path(tf, src, dest)
    finally:
        tf.close()
