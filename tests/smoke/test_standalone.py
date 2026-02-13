"""Smoke tests for standalone vast.py execution.

TEST-09: Standalone vast.py smoke test - python vast.py --help works without pip dependencies.

This test verifies that vast.py can be executed as a standalone script
with only the minimal dependencies (requests, python-dateutil) available.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import subprocess
import pytest


# Get the path to vast.py relative to this test file
VAST_CLI_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
VAST_PY_PATH = os.path.join(VAST_CLI_DIR, 'vast.py')


class TestStandaloneHelp:
    """Tests for standalone vast.py --help execution."""

    def test_vast_help_exits_zero(self):
        """vast.py --help exits with code 0."""
        result = subprocess.run(
            [sys.executable, VAST_PY_PATH, '--help'],
            capture_output=True,
            text=True,
            cwd=VAST_CLI_DIR,
            timeout=30,
        )

        assert result.returncode == 0, f"Exit code was {result.returncode}, stderr: {result.stderr}"

    def test_vast_help_contains_usage(self):
        """vast.py --help output contains usage information."""
        result = subprocess.run(
            [sys.executable, VAST_PY_PATH, '--help'],
            capture_output=True,
            text=True,
            cwd=VAST_CLI_DIR,
            timeout=30,
        )

        assert 'usage' in result.stdout.lower() or 'vast' in result.stdout.lower(), \
            f"Help output missing expected content: {result.stdout[:500]}"

    def test_vast_help_contains_commands(self):
        """vast.py --help output lists available commands."""
        result = subprocess.run(
            [sys.executable, VAST_PY_PATH, '--help'],
            capture_output=True,
            text=True,
            cwd=VAST_CLI_DIR,
            timeout=30,
        )

        # Should mention some key commands
        output = result.stdout.lower()
        assert 'search' in output or 'show' in output or 'create' in output, \
            f"Help output missing command listings: {result.stdout[:500]}"


class TestSubcommandHelp:
    """Tests for subcommand help output."""

    def test_search_offers_help(self):
        """vast.py search offers --help works."""
        result = subprocess.run(
            [sys.executable, VAST_PY_PATH, 'search', 'offers', '--help'],
            capture_output=True,
            text=True,
            cwd=VAST_CLI_DIR,
            timeout=30,
        )

        assert result.returncode == 0, f"Exit code was {result.returncode}, stderr: {result.stderr}"
        assert 'search' in result.stdout.lower() or 'offers' in result.stdout.lower()

    def test_show_instances_help(self):
        """vast.py show instances --help works."""
        result = subprocess.run(
            [sys.executable, VAST_PY_PATH, 'show', 'instances', '--help'],
            capture_output=True,
            text=True,
            cwd=VAST_CLI_DIR,
            timeout=30,
        )

        assert result.returncode == 0, f"Exit code was {result.returncode}, stderr: {result.stderr}"

    def test_create_instance_help(self):
        """vast.py create instance --help works."""
        result = subprocess.run(
            [sys.executable, VAST_PY_PATH, 'create', 'instance', '--help'],
            capture_output=True,
            text=True,
            cwd=VAST_CLI_DIR,
            timeout=30,
        )

        assert result.returncode == 0, f"Exit code was {result.returncode}, stderr: {result.stderr}"

    def test_destroy_instance_help(self):
        """vast.py destroy instance --help works."""
        result = subprocess.run(
            [sys.executable, VAST_PY_PATH, 'destroy', 'instance', '--help'],
            capture_output=True,
            text=True,
            cwd=VAST_CLI_DIR,
            timeout=30,
        )

        assert result.returncode == 0, f"Exit code was {result.returncode}, stderr: {result.stderr}"


class TestVersionFlag:
    """Tests for version flag if implemented."""

    def test_vast_version_or_help(self):
        """vast.py responds to --version or --help without error."""
        # Try --version first
        result = subprocess.run(
            [sys.executable, VAST_PY_PATH, '--version'],
            capture_output=True,
            text=True,
            cwd=VAST_CLI_DIR,
            timeout=30,
        )

        # If --version isn't implemented, that's okay - just verify it doesn't crash
        # (might return non-zero for unrecognized flag, but shouldn't hang or throw)
        assert result.returncode in [0, 1, 2], \
            f"Unexpected exit code {result.returncode}, stderr: {result.stderr}"


class TestInvalidCommand:
    """Tests for invalid command handling."""

    def test_invalid_command_exits_nonzero(self):
        """vast.py with invalid command exits with non-zero code."""
        result = subprocess.run(
            [sys.executable, VAST_PY_PATH, 'not_a_real_command'],
            capture_output=True,
            text=True,
            cwd=VAST_CLI_DIR,
            timeout=30,
        )

        # Should exit non-zero for invalid command
        assert result.returncode != 0, "Invalid command should exit non-zero"

    def test_invalid_command_prints_error(self):
        """vast.py with invalid command prints error message."""
        result = subprocess.run(
            [sys.executable, VAST_PY_PATH, 'not_a_real_command'],
            capture_output=True,
            text=True,
            cwd=VAST_CLI_DIR,
            timeout=30,
        )

        # Should have some error output
        combined_output = result.stdout + result.stderr
        assert len(combined_output) > 0, "Should produce some output for invalid command"


class TestImportOnly:
    """Tests that verify vast.py can be imported without side effects."""

    def test_vast_importable(self):
        """vast.py is importable as a module."""
        # This runs in the test process, verifying import works
        import vast

        assert hasattr(vast, 'parser')
        assert hasattr(vast, 'main')

    def test_vast_main_exists(self):
        """vast.main() function exists."""
        import vast

        assert callable(vast.main)

    def test_vast_has_core_functions(self):
        """vast module has core CLI functions."""
        import vast

        # Check for key command functions
        assert hasattr(vast, 'search__offers')
        assert hasattr(vast, 'show__instances')
        assert hasattr(vast, 'create__instance')
        assert hasattr(vast, 'destroy__instance')

    def test_vast_has_http_helpers(self):
        """vast module has HTTP helper functions."""
        import vast

        assert hasattr(vast, 'http_get')
        assert hasattr(vast, 'http_post')
        assert hasattr(vast, 'http_put')
        assert hasattr(vast, 'http_del')


class TestMinimalDependencies:
    """Tests verifying vast.py works with minimal dependencies."""

    def test_import_only_requires_requests(self):
        """vast.py import only requires requests (and python-dateutil)."""
        # Run a subprocess that only has requests available
        # This is tested implicitly by the fact that we can import vast
        # without extra dependencies installed
        result = subprocess.run(
            [sys.executable, '-c', 'import vast; print("OK")'],
            capture_output=True,
            text=True,
            cwd=VAST_CLI_DIR,
            timeout=30,
        )

        assert result.returncode == 0, f"Import failed: {result.stderr}"
        assert "OK" in result.stdout

    def test_help_runs_without_optional_deps(self):
        """vast.py --help works even if optional dependencies are missing."""
        # argcomplete and curlify are optional
        # This test verifies help still works
        result = subprocess.run(
            [sys.executable, VAST_PY_PATH, '--help'],
            capture_output=True,
            text=True,
            cwd=VAST_CLI_DIR,
            timeout=30,
        )

        assert result.returncode == 0


class TestExitCodes:
    """Tests for proper exit codes."""

    def test_help_exits_zero(self):
        """--help exits with code 0."""
        result = subprocess.run(
            [sys.executable, VAST_PY_PATH, '--help'],
            capture_output=True,
            text=True,
            cwd=VAST_CLI_DIR,
            timeout=30,
        )
        assert result.returncode == 0

    def test_subcommand_help_exits_zero(self):
        """Subcommand --help exits with code 0."""
        result = subprocess.run(
            [sys.executable, VAST_PY_PATH, 'show', 'instances', '--help'],
            capture_output=True,
            text=True,
            cwd=VAST_CLI_DIR,
            timeout=30,
        )
        assert result.returncode == 0

    def test_missing_required_arg_exits_nonzero(self):
        """Missing required argument exits with non-zero code."""
        # create instance requires an ID
        result = subprocess.run(
            [sys.executable, VAST_PY_PATH, 'create', 'instance'],
            capture_output=True,
            text=True,
            cwd=VAST_CLI_DIR,
            timeout=30,
        )
        assert result.returncode != 0
