"""Regression tests for API request and raw output fixes."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestApiKeyHandling:
    """API key should be in headers, not JSON body."""

    def test_no_api_key_in_json_blob(self):
        """api_key should not appear in json_blob assignments."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        # Look for json_blob containing api_key (but not in comments)
        lines = content.split('\n')
        violations = []
        for i, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith('#'):
                continue
            # Check for api_key in json dict literal on same line as json_blob
            if 'json_blob' in line and 'api_key' in line and '=' in line:
                violations.append(f"Line {i}: {line.strip()}")

        assert len(violations) == 0, f"Found api_key in json_blob: {violations}"

    def test_get_endpt_logs_no_api_key_in_body(self):
        """get__endpt_logs should not have api_key in JSON."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        # Find function and check its body
        pattern = r'def get__endpt_logs\(.*?(?=\ndef |\Z)'
        match = re.search(pattern, content, re.DOTALL)
        assert match, "get__endpt_logs function not found"

        func_body = match.group(0)
        # Should not have api_key in any dict literal
        json_lines = [l for l in func_body.split('\n')
                     if 'json_blob' in l and 'api_key' in l and '=' in l
                     and not l.strip().startswith('#')]
        assert len(json_lines) == 0, f"get__endpt_logs has api_key in json_blob: {json_lines}"

    def test_get_wrkgrp_logs_no_api_key_in_body(self):
        """get__wrkgrp_logs should not have api_key in JSON."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        pattern = r'def get__wrkgrp_logs\(.*?(?=\ndef |\Z)'
        match = re.search(pattern, content, re.DOTALL)
        assert match, "get__wrkgrp_logs function not found"

        func_body = match.group(0)
        json_lines = [l for l in func_body.split('\n')
                     if 'json_blob' in l and 'api_key' in l and '=' in l
                     and not l.strip().startswith('#')]
        assert len(json_lines) == 0, f"get__wrkgrp_logs has api_key in json_blob: {json_lines}"

    def test_show_workergroups_no_api_key_in_body(self):
        """show__workergroups should not have api_key in JSON."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        pattern = r'def show__workergroups\(.*?(?=\ndef |\Z)'
        match = re.search(pattern, content, re.DOTALL)
        assert match, "show__workergroups function not found"

        func_body = match.group(0)
        json_lines = [l for l in func_body.split('\n')
                     if 'json_blob' in l and 'api_key' in l and '=' in l
                     and not l.strip().startswith('#')]
        assert len(json_lines) == 0, f"show__workergroups has api_key in json_blob: {json_lines}"

    def test_show_endpoints_no_api_key_in_body(self):
        """show__endpoints should not have api_key in JSON."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        pattern = r'def show__endpoints\(.*?(?=\ndef |\Z)'
        match = re.search(pattern, content, re.DOTALL)
        assert match, "show__endpoints function not found"

        func_body = match.group(0)
        json_lines = [l for l in func_body.split('\n')
                     if 'json_blob' in l and 'api_key' in l and '=' in l
                     and not l.strip().startswith('#')]
        assert len(json_lines) == 0, f"show__endpoints has api_key in json_blob: {json_lines}"


class TestSafeIteration:
    """next() calls should have default to prevent StopIteration."""

    def test_next_calls_have_default(self):
        """All next() calls with generators should have a default parameter."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        # Find next() calls without default
        # Pattern: next(something for something) without a comma before closing
        lines = content.split('\n')
        risky_calls = []
        for i, line in enumerate(lines, 1):
            if 'next(' in line and not line.strip().startswith('#'):
                # Simple heuristic: if line has next( with 'for' inside but no comma
                # This catches: next(x for x in y) but not next((x for x in y), None)
                match = re.search(r'next\(\s*[^,)]+\s+for\s+[^,)]+\)', line)
                if match:
                    risky_calls.append(f"Line {i}: {line.strip()}")

        assert len(risky_calls) == 0, f"Found next() without default: {risky_calls}"

    def test_show_clusters_next_has_default(self):
        """show__clusters manager_node lookup should have default."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        pattern = r'def show__clusters\(.*?(?=\ndef |\Z)'
        match = re.search(pattern, content, re.DOTALL)
        assert match, "show__clusters function not found"

        func_body = match.group(0)

        # Should have next(..., None) pattern - may be multiline with nested parens
        assert 'next(' in func_body, "show__clusters should use next()"
        # Check for manager_node = next(..., None) with multiline and nested parens
        # The pattern has: next(\n(generator),\nNone\n)
        has_none_default = re.search(r'manager_node\s*=\s*next\s*\(.*?,\s*None\s*\)', func_body, re.DOTALL)
        assert has_none_default, "show__clusters next() should have None default"

    def test_show_clusters_handles_missing_manager(self):
        """show__clusters should handle case when no manager node exists."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        pattern = r'def show__clusters\(.*?(?=\ndef |\Z)'
        match = re.search(pattern, content, re.DOTALL)
        assert match, "show__clusters function not found"

        func_body = match.group(0)

        # Should check for None manager_node
        assert 'manager_node is None' in func_body or 'if manager_node is None' in func_body, \
            "show__clusters should check for None manager_node"


class TestTransferCredit:
    """--transfer_credit should be implemented or removed from docs."""

    def test_transfer_credit_not_in_create_team_epilog(self):
        """create team epilog should not mention --transfer_credit."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        # Find create__team function and its decorator
        pattern = r'@parser\.command\([^)]*argument\([^)]*team_name[^)]*\)[^)]*\)[^@]*def create__team'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            decorator_and_func = match.group(0)
            # Should not mention --transfer_credit as a flag
            assert '--transfer_credit' not in decorator_and_func, \
                "create team should not document --transfer_credit as a flag"

    def test_transfer_credit_consistency(self):
        """If --transfer_credit is mentioned, it should be documented correctly."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        # Find create__team decorator/epilog section
        pattern = r'@parser\.command\(\s*argument\("--team_name".*?def create__team'
        match = re.search(pattern, content, re.DOTALL)

        if match:
            section = match.group(0)
            # If transfer_credit is mentioned at all, it should NOT be as --transfer_credit flag
            if 'transfer_credit' in section.lower():
                # Should be pointing to the separate command, not documenting a flag
                assert 'vastai transfer credit' in section or '--transfer_credit' not in section, \
                    "transfer_credit should point to 'vastai transfer credit' command, not a flag"

    def test_transfer_credit_command_exists(self):
        """The transfer__credit command should exist as separate command."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        # transfer__credit should exist as its own command
        assert 'def transfer__credit' in content, \
            "transfer__credit should exist as a separate command"

        # It should have proper argument decorators - multiline decorator
        # Look for recipient and amount in argument() calls before def transfer__credit
        pattern = r'@parser\.command\(.*?def transfer__credit'
        match = re.search(pattern, content, re.DOTALL)
        assert match, "transfer__credit should have @parser.command decorator"
        decorator_section = match.group(0)
        assert 'recipient' in decorator_section, "transfer__credit should have recipient argument"
        assert 'amount' in decorator_section, "transfer__credit should have amount argument"
