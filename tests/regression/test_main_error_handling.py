"""Regression tests for code quality fixes.

- No Python builtins (id, sum) should be shadowed by local variables
- strip('-') should not be used for prefix removal (use startswith + lstrip)
- Error messages should reference correct field name
- Unused variables should be removed
"""
import re
import sys
from pathlib import Path

# Add vast-cli to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestVariableShadowing:
    """No Python builtins should be shadowed by local variable assignments."""

    def test_no_id_shadowing(self):
        """Local variable 'id' should not shadow builtin.

        Note: keyword args in argparse.Namespace() like id=value are NOT shadowing.
        """
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        # Find all assignments to bare 'id' (not id= which is keyword arg)
        # Pattern: whitespace + id + optional space + = + not = (not ==)
        # This should NOT match lines like "id=ask_contract_id," in Namespace()
        matches = re.findall(r'^\s+id\s+=[^=]', content, re.MULTILINE)

        assert len(matches) == 0, (
            f"Found {len(matches)} instances of 'id' shadowing builtin. "
            f"These should be renamed to domain-specific names like instance_id, "
            f"workergroup_id, etc. First few matches: {matches[:5]}"
        )

    def test_no_sum_function_shadowing(self):
        """Function 'sum' should not shadow builtin.

        The custom sum function should be renamed to sum_field or similar.
        """
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        # Check for def sum( function definition
        matches = re.findall(r'^def sum\s*\(', content, re.MULTILINE)

        assert len(matches) == 0, (
            f"Found def sum() which shadows Python builtin. "
            f"Should be renamed to sum_field() or similar."
        )

    def test_sum_field_function_exists(self):
        """The renamed sum_field function should exist."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        # Check for def sum_field( function definition
        assert 'def sum_field(' in content, (
            "Expected sum_field() function to exist after renaming from sum()"
        )

    def test_domain_specific_id_names_used(self):
        """Verify domain-specific id names are used instead of bare 'id'."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        expected_patterns = [
            'workergroup_id = args.id',
            'endpoint_id = args.id',
            'volume_id = args.id',
        ]

        for pattern in expected_patterns:
            assert pattern in content, (
                f"Expected domain-specific name pattern '{pattern}' not found. "
                f"Bare 'id' may not have been renamed properly."
            )


class TestStringMethodFixes:
    """strip('-') should not be used for prefix removal."""

    def test_no_strip_dash_for_direction(self):
        """strip('-') removes from both ends - should use startswith + lstrip."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        # .strip("-") or .strip('-') should not appear for direction parsing
        matches = re.findall(r'name\.strip\(["\'][-+]["\']', content)

        assert len(matches) == 0, (
            f"Found {len(matches)} instances of name.strip('-') or name.strip('+'). "
            f"These should use startswith() + lstrip() instead: {matches}"
        )

    def test_direction_parsing_uses_startswith(self):
        """Sort direction parsing should use startswith, not strip comparison."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        # Should find startswith("-") for direction checks
        has_startswith_minus = 'name.startswith("-")' in content
        has_startswith_plus = 'name.startswith("+")' in content

        assert has_startswith_minus, (
            "Expected name.startswith('-') for descending sort direction parsing"
        )
        assert has_startswith_plus, (
            "Expected name.startswith('+') for ascending sort direction parsing"
        )

    def test_direction_parsing_uses_lstrip(self):
        """After detecting prefix, should use lstrip to remove it."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        # Should find lstrip("-") and lstrip("+")
        has_lstrip_minus = 'name.lstrip("-")' in content
        has_lstrip_plus = 'name.lstrip("+")' in content

        assert has_lstrip_minus, (
            "Expected name.lstrip('-') for removing descending prefix"
        )
        assert has_lstrip_plus, (
            "Expected name.lstrip('+') for removing ascending prefix"
        )

    def test_elif_structure_for_direction_parsing(self):
        """Direction parsing should use elif, not two separate if statements.

        Using two separate if statements means a field like '-score' would first
        match startswith('-') then incorrectly also check startswith('+').
        """
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        # Look for the correct pattern: if startswith("-") ... elif startswith("+")
        # Not: if startswith("-") ... if startswith("+")
        pattern = r'if name\.startswith\("-"\):.*?elif name\.startswith\("\+"\):'
        matches = re.findall(pattern, content, re.DOTALL)

        assert len(matches) >= 4, (
            f"Expected at least 4 occurrences of correct if/elif pattern for "
            f"direction parsing (in search__offers, search__instances, "
            f"search__volumes, search__network_volumes), found {len(matches)}"
        )


class TestErrorMessages:
    """Error messages should reference correct field."""

    def test_start_date_error_message_correct(self):
        """Error for start_date should say 'start date', not 'end date'."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        # Should not have "start date" error saying "Ignoring end date"
        bad_pattern = re.search(
            r'Invalid start date.*Ignoring end date',
            content,
            re.IGNORECASE
        )

        assert bad_pattern is None, (
            "Found misleading error message - start_date error mentions 'Ignoring end date'. "
            "Should say 'Ignoring start date' instead."
        )

    def test_start_date_error_says_start_date(self):
        """Start date errors should reference start date."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        # Should find "Invalid start date" + "Ignoring start date" pattern
        correct_pattern = re.search(
            r'Invalid start date.*Ignoring start date',
            content,
            re.IGNORECASE
        )

        assert correct_pattern is not None, (
            "Expected start_date error message to say 'Ignoring start date'"
        )


class TestUnusedVariables:
    """Unused variables should be removed."""

    def test_no_unused_date_txt_in_show_earnings(self):
        """In show__earnings, date_txt variables should not be assigned if unused.

        Note: date_txt variables ARE used in invoice functions, just not in show__earnings.
        """
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        content = vast_path.read_text(encoding='utf-8')

        # Find the show__earnings function
        show_earnings_match = re.search(
            r'def show__earnings\(args\):.*?(?=\ndef |$)',
            content,
            re.DOTALL
        )

        assert show_earnings_match is not None, "Could not find show__earnings function"

        show_earnings_code = show_earnings_match.group(0)

        # Check that end_date_txt and start_date_txt are not assigned in this function
        has_end_date_txt = 'end_date_txt' in show_earnings_code
        has_start_date_txt = 'start_date_txt' in show_earnings_code

        assert not has_end_date_txt, (
            "Found unused end_date_txt assignment in show__earnings. "
            "This variable is assigned but never used in this function."
        )
        assert not has_start_date_txt, (
            "Found unused start_date_txt assignment in show__earnings. "
            "This variable is assigned but never used in this function."
        )
