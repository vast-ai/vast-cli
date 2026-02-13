"""
MkDocs hooks for auto-generating documentation.

This module is loaded by MkDocs via the hooks configuration and runs
the CLI docs generator before each build.
"""

import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("mkdocs.hooks")


def on_pre_build(config):
    """Run CLI docs generator before MkDocs builds the site."""
    repo_root = Path(config["docs_dir"]).parent
    script = repo_root / "scripts" / "generate_cli_docs.py"

    if not script.exists():
        log.warning(f"CLI docs generator not found: {script}")
        return

    log.info("Generating CLI command reference...")

    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            # Extract stats from output
            for line in result.stdout.strip().split("\n"):
                if line:
                    log.info(f"  {line}")
        else:
            log.error(f"CLI docs generation failed: {result.stderr}")

    except subprocess.TimeoutExpired:
        log.error("CLI docs generation timed out")
    except Exception as e:
        log.error(f"CLI docs generation error: {e}")
