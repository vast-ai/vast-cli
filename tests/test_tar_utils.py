from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import subprocess
import tarfile
import tempfile

import pytest

from vastai.serverless.remote.base import Config
from vastai.serverless.remote.utils import (
    _sanitize_info,
    _scan_python_line,
    add_file,
    add_folder,
    add_path,
    add_string,
    compute_deployment_hash,
    create_deployment_tarball,
    deployment_arcname,
    filter_ignored_lines,
    is_python_module,
    is_python_package,
    read_file_for_hash,
    serialize_config,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_config():
    return Config(
        name="test-deployment",
        pip_installs=["torch", "numpy"],
        apt_gets=["libgl1"],
        envs=[["KEY", "VALUE"]],
        runs=["echo hello", ["bash", "-c", "echo world"]],
    )


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a tmp_path with some files pre-created."""
    (tmp_path / "hello.txt").write_text("hello world")
    (tmp_path / "script.py").write_text("x = 1\n")
    return tmp_path


@pytest.fixture
def module_path(tmp_path):
    """A single .py file acting as a deployment module."""
    p = tmp_path / "my_deploy.py"
    p.write_text("def handler(): pass\n")
    return str(p)


@pytest.fixture
def package_path(tmp_path):
    """A Python package directory acting as a deployment."""
    pkg = tmp_path / "my_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "main.py").write_text("def handler(): pass\n")
    sub = pkg / "sub"
    sub.mkdir()
    (sub / "__init__.py").write_text("")
    (sub / "helper.py").write_text("def help(): pass\n")
    return str(pkg)


@pytest.fixture
def tar_path():
    """Provide a closed NamedTemporaryFile path, matching the deploy.py pattern."""
    with tempfile.NamedTemporaryFile(delete_on_close=False, suffix=".tar") as f:
        path = f.name
        f.close()
        yield path
    if os.path.exists(path):
        os.unlink(path)


# ---------------------------------------------------------------------------
# Helper to open a writable tar at a given path (for add_* unit tests)
# ---------------------------------------------------------------------------


def _write_tar(path: str) -> tarfile.TarFile:
    """Open a new tarball for writing at the given path."""
    return tarfile.open(path, "w:")


def _open_tar_from_path(path: str) -> tarfile.TarFile:
    """Open a tarball for reading (detect compression)."""
    return tarfile.open(path, "r:*")


# ---------------------------------------------------------------------------
# _sanitize_info
# ---------------------------------------------------------------------------


class TestSanitizeInfo:
    def test_sets_root_ownership(self):
        info = tarfile.TarInfo(name="test")
        info.uid = 1000
        info.gid = 1000
        info.uname = "user"
        info.gname = "user"
        result = _sanitize_info(info)
        assert result is info
        assert info.uid == 0
        assert info.gid == 0
        assert info.uname == "root"
        assert info.gname == "root"


# ---------------------------------------------------------------------------
# add_file / add_folder / add_string / add_path
# ---------------------------------------------------------------------------


class TestAddFile:
    def test_file_appears_at_arcname(self, tmp_dir, tar_path):
        tf = _write_tar(tar_path)
        add_file(tf, str(tmp_dir / "hello.txt"), "dest/hello.txt")
        tf.close()
        with _open_tar_from_path(tar_path) as rtf:
            assert "dest/hello.txt" in rtf.getnames()
            assert rtf.extractfile("dest/hello.txt").read() == b"hello world"

    def test_uid_gid_sanitized(self, tmp_dir, tar_path):
        tf = _write_tar(tar_path)
        add_file(tf, str(tmp_dir / "hello.txt"), "f.txt")
        tf.close()
        with _open_tar_from_path(tar_path) as rtf:
            info = rtf.getmember("f.txt")
            assert info.uid == 0
            assert info.gid == 0


class TestAddFolder:
    def test_recursive_contents(self, package_path, tar_path):
        tf = _write_tar(tar_path)
        add_folder(tf, package_path, "pkg")
        tf.close()
        with _open_tar_from_path(tar_path) as rtf:
            names = rtf.getnames()
            assert "pkg" in names
            assert "pkg/__init__.py" in names
            assert "pkg/main.py" in names
            assert "pkg/sub" in names
            assert "pkg/sub/__init__.py" in names
            assert "pkg/sub/helper.py" in names

    def test_uid_gid_sanitized_on_all_entries(self, package_path, tar_path):
        tf = _write_tar(tar_path)
        add_folder(tf, package_path, "pkg")
        tf.close()
        with _open_tar_from_path(tar_path) as rtf:
            for member in rtf.getmembers():
                assert member.uid == 0
                assert member.gid == 0


class TestAddString:
    def test_content_roundtrip(self, tar_path):
        tf = _write_tar(tar_path)
        add_string(tf, "hello world", "msg.txt")
        tf.close()
        with _open_tar_from_path(tar_path) as rtf:
            assert rtf.extractfile("msg.txt").read() == b"hello world"

    def test_default_mode(self, tar_path):
        tf = _write_tar(tar_path)
        add_string(tf, "x", "f.txt")
        tf.close()
        with _open_tar_from_path(tar_path) as rtf:
            assert rtf.getmember("f.txt").mode == 0o644

    def test_executable_mode(self, tar_path):
        tf = _write_tar(tar_path)
        add_string(tf, "#!/bin/bash", "run.sh", executable=True)
        tf.close()
        with _open_tar_from_path(tar_path) as rtf:
            assert rtf.getmember("run.sh").mode == 0o755


class TestAddPath:
    def test_dispatches_to_file(self, tmp_dir, tar_path):
        tf = _write_tar(tar_path)
        add_path(tf, str(tmp_dir / "hello.txt"), "f.txt")
        tf.close()
        with _open_tar_from_path(tar_path) as rtf:
            assert rtf.extractfile("f.txt").read() == b"hello world"

    def test_dispatches_to_folder(self, package_path, tar_path):
        tf = _write_tar(tar_path)
        add_path(tf, package_path, "pkg")
        tf.close()
        with _open_tar_from_path(tar_path) as rtf:
            assert "pkg/__init__.py" in rtf.getnames()

    def test_raises_on_nonexistent(self, tar_path):
        tf = _write_tar(tar_path)
        try:
            with pytest.raises(FileNotFoundError):
                add_path(tf, "/no/such/path", "x")
        finally:
            tf.close()


# ---------------------------------------------------------------------------
# serialize_config
# ---------------------------------------------------------------------------


class TestSerializeConfig:
    def test_roundtrips_through_json(self, sample_config):
        s = serialize_config(sample_config)
        d = json.loads(s)
        assert d["name"] == "test-deployment"
        assert d["pip_installs"] == ["torch", "numpy"]
        assert d["apt_gets"] == ["libgl1"]
        assert d["envs"] == [["KEY", "VALUE"]]
        assert d["runs"] == ["echo hello", ["bash", "-c", "echo world"]]

    def test_tuples_become_lists(self):
        config = Config(
            name="t",
            pip_installs=[],
            apt_gets=[],
            envs=[("A", "B")],
            runs=[("ls", "-la")],
        )
        d = json.loads(serialize_config(config))
        assert d["envs"] == [["A", "B"]]
        assert d["runs"] == [["ls", "-la"]]


# ---------------------------------------------------------------------------
# is_python_package / is_python_module / deployment_arcname
# ---------------------------------------------------------------------------


class TestIsPythonPackage:
    def test_true_for_package(self, package_path):
        assert is_python_package(package_path) is True

    def test_false_for_plain_directory(self, tmp_path):
        d = tmp_path / "not_a_pkg"
        d.mkdir()
        assert is_python_package(str(d)) is False

    def test_false_for_file(self, module_path):
        assert is_python_package(module_path) is False

    def test_false_for_nonexistent(self):
        assert is_python_package("/no/such/path") is False


class TestIsPythonModule:
    def test_true_for_py_file(self, module_path):
        assert is_python_module(module_path) is True

    def test_false_for_non_py_file(self, tmp_dir):
        assert is_python_module(str(tmp_dir / "hello.txt")) is False

    def test_false_for_directory(self, package_path):
        assert is_python_module(package_path) is False

    def test_false_for_nonexistent(self):
        assert is_python_module("/no/such/file.py") is False


class TestDeploymentArcname:
    def test_package_arcname(self, package_path):
        assert deployment_arcname(package_path) == "./deployment"

    def test_module_arcname(self, module_path):
        assert deployment_arcname(module_path) == "./deployment.py"

    def test_raises_for_plain_directory(self, tmp_path):
        d = tmp_path / "not_a_pkg"
        d.mkdir()
        with pytest.raises(ValueError, match="neither a Python package"):
            deployment_arcname(str(d))

    def test_raises_for_non_py_file(self, tmp_dir):
        with pytest.raises(ValueError, match="neither a Python package"):
            deployment_arcname(str(tmp_dir / "hello.txt"))

    def test_raises_for_nonexistent(self):
        with pytest.raises(ValueError, match="neither a Python package"):
            deployment_arcname("/no/such/path")


# ---------------------------------------------------------------------------
# _scan_python_line / filter_ignored_lines
# ---------------------------------------------------------------------------


class TestScanPythonLine:
    def test_bare_marker(self):
        hit, state = _scan_python_line(b"x = 1  #!VAST_IGNORE_CHANGES", None)
        assert hit is True
        assert state is None

    def test_marker_with_spaces(self):
        hit, _ = _scan_python_line(b"x = 1  #  !VAST_IGNORE_CHANGES  ", None)
        assert hit is True

    def test_marker_alone_on_line(self):
        hit, _ = _scan_python_line(b"#!VAST_IGNORE_CHANGES", None)
        assert hit is True

    def test_partial_comment_not_matched(self):
        hit, _ = _scan_python_line(b"# something !VAST_IGNORE_CHANGES", None)
        assert hit is False

    def test_trailing_text_not_matched(self):
        hit, _ = _scan_python_line(b"# !VAST_IGNORE_CHANGES extra", None)
        assert hit is False

    def test_inside_single_quoted_string(self):
        hit, _ = _scan_python_line(b'x = "#!VAST_IGNORE_CHANGES"', None)
        assert hit is False

    def test_inside_double_quoted_string(self):
        hit, _ = _scan_python_line(b"x = '#!VAST_IGNORE_CHANGES'", None)
        assert hit is False

    def test_after_string_with_hash(self):
        hit, _ = _scan_python_line(b'x = "a#b"  #!VAST_IGNORE_CHANGES', None)
        assert hit is True

    def test_triple_quote_open_closes_same_line(self):
        hit, state = _scan_python_line(b'x = """hello"""  #!VAST_IGNORE_CHANGES', None)
        assert hit is True
        assert state is None

    def test_triple_quote_opens_multiline(self):
        hit, state = _scan_python_line(b'x = """start of string', None)
        assert hit is False
        assert state == b'"""'

    def test_inside_multiline_no_close(self):
        hit, state = _scan_python_line(b"still in string #!VAST_IGNORE_CHANGES", b'"""')
        assert hit is False
        assert state == b'"""'

    def test_multiline_closes(self):
        hit, state = _scan_python_line(b'end of string"""', b'"""')
        assert hit is False
        assert state is None

    def test_multiline_closes_then_comment(self):
        hit, state = _scan_python_line(b'end"""  #!VAST_IGNORE_CHANGES', b'"""')
        assert hit is True
        assert state is None

    def test_single_quote_triple(self):
        hit, state = _scan_python_line(b"x = '''start", None)
        assert hit is False
        assert state == b"'''"

    def test_single_quote_triple_closes(self):
        hit, state = _scan_python_line(b"end'''  #!VAST_IGNORE_CHANGES", b"'''")
        assert hit is True

    def test_escaped_quote_in_single_string(self):
        hit, _ = _scan_python_line(rb'x = "hello\"#!VAST_IGNORE_CHANGES"', None)
        assert hit is False

    def test_escaped_backslash_before_close(self):
        # String is "hello\\" (ends with literal backslash), then comment follows
        hit, _ = _scan_python_line(rb'x = "hello\\"  #!VAST_IGNORE_CHANGES', None)
        assert hit is True

    def test_plain_code_no_match(self):
        hit, state = _scan_python_line(b"x = 1 + 2", None)
        assert hit is False
        assert state is None


class TestFilterIgnoredLines:
    def test_strips_marker_lines(self):
        data = b"keep\nx = 1  #!VAST_IGNORE_CHANGES\nalso keep"
        assert filter_ignored_lines(data) == b"keep\nalso keep"

    def test_preserves_non_marker_lines(self):
        data = b"a\nb\nc"
        assert filter_ignored_lines(data) == data

    def test_multiline_string_not_filtered(self):
        data = b'x = """\n#!VAST_IGNORE_CHANGES\n"""\nkeep'
        assert filter_ignored_lines(data) == data

    def test_multiple_markers(self):
        data = b"a  #!VAST_IGNORE_CHANGES\nkeep\nb  #!VAST_IGNORE_CHANGES"
        assert filter_ignored_lines(data) == b"keep"

    def test_multiline_spans_correctly(self):
        lines = [
            b"before",
            b'x = """',
            b"#!VAST_IGNORE_CHANGES",
            b"still in string",
            b'"""',
            b"after  #!VAST_IGNORE_CHANGES",
            b"end",
        ]
        data = b"\n".join(lines)
        result = filter_ignored_lines(data)
        # The marker inside the triple-quoted string is kept;
        # the marker after the string closes is stripped.
        expected = b"\n".join(
            [
                b"before",
                b'x = """',
                b"#!VAST_IGNORE_CHANGES",
                b"still in string",
                b'"""',
                b"end",
            ]
        )
        assert result == expected


# ---------------------------------------------------------------------------
# read_file_for_hash
# ---------------------------------------------------------------------------


class TestReadFileForHash:
    def test_no_filter_returns_raw(self, tmp_path):
        p = tmp_path / "test.py"
        p.write_bytes(b"x = 1  #!VAST_IGNORE_CHANGES\n")
        assert (
            read_file_for_hash(str(p), filter_comments=False)
            == b"x = 1  #!VAST_IGNORE_CHANGES\n"
        )

    def test_filter_on_py_file(self, tmp_path):
        p = tmp_path / "test.py"
        p.write_bytes(b"keep\nx = 1  #!VAST_IGNORE_CHANGES\nalso keep")
        assert read_file_for_hash(str(p), filter_comments=True) == b"keep\nalso keep"

    def test_filter_ignored_on_non_py(self, tmp_path):
        p = tmp_path / "data.txt"
        p.write_bytes(b"#!VAST_IGNORE_CHANGES\n")
        assert (
            read_file_for_hash(str(p), filter_comments=True)
            == b"#!VAST_IGNORE_CHANGES\n"
        )


# ---------------------------------------------------------------------------
# hash determinism and sensitivity
# ---------------------------------------------------------------------------


class TestHashUpdateDirectory:
    def test_deterministic(self, package_path):
        h1 = hashlib.sha256()
        h2 = hashlib.sha256()
        from vastai.serverless.remote.utils import hash_update_directory

        hash_update_directory(h1, package_path, "pkg")
        hash_update_directory(h2, package_path, "pkg")
        assert h1.hexdigest() == h2.hexdigest()

    def test_content_change_changes_hash(self, package_path):
        from vastai.serverless.remote.utils import hash_update_directory

        h1 = hashlib.sha256()
        hash_update_directory(h1, package_path, "pkg")
        # Modify a file
        with open(os.path.join(package_path, "main.py"), "w") as f:
            f.write("def handler(): return 42\n")
        h2 = hashlib.sha256()
        hash_update_directory(h2, package_path, "pkg")
        assert h1.hexdigest() != h2.hexdigest()


# ---------------------------------------------------------------------------
# compute_deployment_hash
# ---------------------------------------------------------------------------


class TestComputeDeploymentHash:
    def test_deterministic(self, sample_config, module_path):
        h1 = compute_deployment_hash(sample_config, module_path)
        h2 = compute_deployment_hash(sample_config, module_path)
        assert h1 == h2

    def test_config_change_changes_hash(self, sample_config, module_path):
        h1 = compute_deployment_hash(sample_config, module_path)
        sample_config.name = "different"
        h2 = compute_deployment_hash(sample_config, module_path)
        assert h1 != h2

    def test_deployment_change_changes_hash(self, sample_config, module_path):
        h1 = compute_deployment_hash(sample_config, module_path)
        with open(module_path, "w") as f:
            f.write("def handler(): return 42\n")
        h2 = compute_deployment_hash(sample_config, module_path)
        assert h1 != h2

    def test_extra_file_change_changes_hash(self, sample_config, module_path, tmp_path):
        extra = tmp_path / "extra.txt"
        extra.write_text("v1")
        h1 = compute_deployment_hash(
            sample_config, module_path, [(str(extra), "/opt/extra.txt")]
        )
        extra.write_text("v2")
        h2 = compute_deployment_hash(
            sample_config, module_path, [(str(extra), "/opt/extra.txt")]
        )
        assert h1 != h2

    def test_ignore_marker_in_deployment_does_not_change_hash(
        self, sample_config, tmp_path
    ):
        p = tmp_path / "deploy.py"
        p.write_text("x = 1  #!VAST_IGNORE_CHANGES\ndef handler(): pass\n")
        h1 = compute_deployment_hash(sample_config, str(p))
        p.write_text("x = 999  #!VAST_IGNORE_CHANGES\ndef handler(): pass\n")
        h2 = compute_deployment_hash(sample_config, str(p))
        assert h1 == h2

    def test_ignore_marker_in_extra_py_still_changes_hash(
        self, sample_config, module_path, tmp_path
    ):
        extra = tmp_path / "lib.py"
        extra.write_text("x = 1  #!VAST_IGNORE_CHANGES\n")
        h1 = compute_deployment_hash(
            sample_config, module_path, [(str(extra), "/opt/lib.py")]
        )
        extra.write_text("x = 999  #!VAST_IGNORE_CHANGES\n")
        h2 = compute_deployment_hash(
            sample_config, module_path, [(str(extra), "/opt/lib.py")]
        )
        assert h1 != h2

    def test_works_with_package(self, sample_config, package_path):
        h = compute_deployment_hash(sample_config, package_path)
        assert isinstance(h, str) and len(h) == 64


# ---------------------------------------------------------------------------
# create_deployment_tarball
# ---------------------------------------------------------------------------


class TestCreateDeploymentTarball:
    def test_contains_config_json(self, sample_config, module_path, tar_path):
        create_deployment_tarball(tar_path, sample_config, module_path, compress=False)
        with _open_tar_from_path(tar_path) as rtf:
            data = json.loads(rtf.extractfile("./config.json").read())
            assert data["name"] == "test-deployment"

    def test_module_becomes_deployment_py(self, sample_config, module_path, tar_path):
        create_deployment_tarball(tar_path, sample_config, module_path, compress=False)
        with _open_tar_from_path(tar_path) as rtf:
            assert "./deployment.py" in rtf.getnames()
            content = rtf.extractfile("./deployment.py").read()
            assert b"def handler" in content

    def test_package_becomes_deployment_dir(self, sample_config, package_path, tar_path):
        create_deployment_tarball(tar_path, sample_config, package_path, compress=False)
        with _open_tar_from_path(tar_path) as rtf:
            names = rtf.getnames()
            assert "./deployment" in names
            assert "./deployment/__init__.py" in names
            assert "./deployment/main.py" in names
            assert "./deployment/sub/helper.py" in names

    def test_extra_files_absolute_dest_paths(self, sample_config, module_path, tmp_dir, tar_path):
        extras = [
            (str(tmp_dir / "hello.txt"), "/opt/data/hello.txt"),
            (str(tmp_dir / "script.py"), "/opt/scripts/run.py"),
        ]
        create_deployment_tarball(
            tar_path, sample_config, module_path, extras, compress=False
        )
        with _open_tar_from_path(tar_path) as rtf:
            names = rtf.getnames()
            assert "/opt/data/hello.txt" in names
            assert "/opt/scripts/run.py" in names

    def test_extra_files_relative_dest_paths(self, sample_config, module_path, tmp_dir, tar_path):
        extras = [
            (str(tmp_dir / "hello.txt"), "data/hello.txt"),
            (str(tmp_dir / "script.py"), "./scripts/run.py"),
        ]
        create_deployment_tarball(
            tar_path, sample_config, module_path, extras, compress=False
        )
        with _open_tar_from_path(tar_path) as rtf:
            names = rtf.getnames()
            assert "data/hello.txt" in names
            assert "./scripts/run.py" in names

    def test_compressed_tarball_is_valid(self, sample_config, module_path, tar_path):
        create_deployment_tarball(tar_path, sample_config, module_path, compress=True)
        with tarfile.open(tar_path, "r:gz") as rtf:
            assert "./config.json" in rtf.getnames()

    def test_uncompressed_tarball_is_valid(self, sample_config, module_path, tar_path):
        create_deployment_tarball(tar_path, sample_config, module_path, compress=False)
        with tarfile.open(tar_path, "r:*") as rtf:
            assert "./config.json" in rtf.getnames()

    def test_tar_extract_module_deployment(self, sample_config, module_path, tmp_path, tar_path):
        create_deployment_tarball(tar_path, sample_config, module_path, compress=False)
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()
        subprocess.run(
            ["tar", "-xPf", tar_path, "-C", str(extract_dir)],
            check=True,
        )
        assert (extract_dir / "config.json").is_file()
        config_data = json.loads((extract_dir / "config.json").read_text())
        assert config_data["name"] == "test-deployment"
        assert (extract_dir / "deployment.py").is_file()
        assert "def handler" in (extract_dir / "deployment.py").read_text()

    def test_tar_extract_package_deployment(
        self, sample_config, package_path, tmp_path, tar_path
    ):
        create_deployment_tarball(tar_path, sample_config, package_path, compress=False)
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()
        subprocess.run(
            ["tar", "-xPf", tar_path, "-C", str(extract_dir)],
            check=True,
        )
        assert (extract_dir / "deployment" / "__init__.py").is_file()
        assert (extract_dir / "deployment" / "main.py").is_file()
        assert (extract_dir / "deployment" / "sub" / "helper.py").is_file()

    def test_tar_extract_absolute_extra_files(
        self, sample_config, module_path, tmp_dir, tmp_path, tar_path
    ):
        abs_dest = str(tmp_path / "abs_output" / "data" / "hello.txt")
        extras = [
            (str(tmp_dir / "hello.txt"), abs_dest),
        ]
        create_deployment_tarball(
            tar_path, sample_config, module_path, extras, compress=False
        )
        subprocess.run(["tar", "-xPf", tar_path], check=True)
        assert os.path.isfile(abs_dest)
        with open(abs_dest) as f:
            assert f.read() == "hello world"
        os.unlink(abs_dest)

    def test_tar_extract_relative_extra_files(
        self, sample_config, module_path, tmp_dir, tmp_path, tar_path
    ):
        extras = [
            (str(tmp_dir / "hello.txt"), "data/hello.txt"),
        ]
        create_deployment_tarball(
            tar_path, sample_config, module_path, extras, compress=False
        )
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()
        subprocess.run(
            ["tar", "-xPf", tar_path, "-C", str(extract_dir)],
            check=True,
        )
        extracted = extract_dir / "data" / "hello.txt"
        assert extracted.is_file()
        assert extracted.read_text() == "hello world"

    def test_tar_extract_compressed(self, sample_config, module_path, tmp_path, tar_path):
        create_deployment_tarball(tar_path, sample_config, module_path, compress=True)
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()
        subprocess.run(
            ["tar", "-xPzf", tar_path, "-C", str(extract_dir)],
            check=True,
        )
        assert (extract_dir / "config.json").is_file()
        assert (extract_dir / "deployment.py").is_file()

    def test_tarball_closed_on_error(self, sample_config, tmp_path, tar_path):
        bad_path = str(tmp_path / "nonexistent.py")
        with pytest.raises(ValueError, match="neither a Python package"):
            create_deployment_tarball(tar_path, sample_config, bad_path)
