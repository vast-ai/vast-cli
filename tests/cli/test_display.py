"""Tests for vastai/cli/display.py — display_table, field tuple validation, deindent."""

import pytest
from vastai.cli.display import (
    deindent, display_table, translate_null_strings_to_blanks, strip_strings,
    displayable_fields, instance_fields, machine_fields, volume_fields,
    cluster_fields, overlay_fields, audit_log_fields, scheduled_jobs_fields,
    invoice_fields, user_fields, connection_fields,
)


class TestDeindent:
    def test_basic_deindent(self):
        msg = """
            Hello
            World
        """
        result = deindent(msg, add_separator=False)
        assert "Hello" in result
        assert "World" in result
        # Leading whitespace should be removed
        lines = result.strip().split("\n")
        for line in lines:
            if line.strip():
                assert not line.startswith("            ")

    def test_with_separator(self):
        msg = """
            Hello
        """
        result = deindent(msg, add_separator=True)
        assert "_" in result  # separator line


class TestTranslateNullStrings:
    def test_empty_string_becomes_space(self):
        d = {"a": "", "b": "hello"}
        result = translate_null_strings_to_blanks(d)
        assert result["a"] == " "
        assert result["b"] == "hello"


class TestStripStrings:
    def test_strips_string(self):
        assert strip_strings("  hello  ") == "hello"

    def test_strips_in_dict(self):
        result = strip_strings({"k": "  v  "})
        assert result["k"] == "v"

    def test_strips_in_list(self):
        result = strip_strings(["  a  ", "  b  "])
        assert result == ["a", "b"]

    def test_leaves_non_string(self):
        assert strip_strings(42) == 42


class TestDisplayTable:
    def test_runs_without_error(self, capsys):
        rows = [
            {"id": 1, "gpu_name": "RTX_3090", "num_gpus": 2},
        ]
        fields = (
            ("id", "ID", "{}", None, True),
            ("gpu_name", "GPU", "{}", None, True),
            ("num_gpus", "N", "{}", None, False),
        )
        display_table(rows, fields)
        captured = capsys.readouterr()
        assert "ID" in captured.out
        assert "GPU" in captured.out

    def test_handles_missing_fields(self, capsys):
        rows = [{"id": 1}]
        fields = (
            ("id", "ID", "{}", None, True),
            ("missing_field", "Missing", "{}", None, True),
        )
        display_table(rows, fields)
        captured = capsys.readouterr()
        assert "-" in captured.out

    def test_applies_conversion_functions(self, capsys):
        rows = [{"ram": 16000}]
        fields = (
            ("ram", "RAM_GB", "{:0.1f}", lambda x: x / 1000, False),
        )
        display_table(rows, fields)
        captured = capsys.readouterr()
        assert "16.0" in captured.out

    def test_empty_rows(self, capsys):
        fields = (
            ("id", "ID", "{}", None, True),
        )
        display_table([], fields)
        captured = capsys.readouterr()
        assert "ID" in captured.out


class TestFieldDefinitions:
    """All field definition tuples are 5-tuples with correct types."""

    ALL_FIELD_DEFS = [
        ("displayable_fields", displayable_fields),
        ("instance_fields", instance_fields),
        ("machine_fields", machine_fields),
        ("volume_fields", volume_fields),
        ("cluster_fields", cluster_fields),
        ("overlay_fields", overlay_fields),
        ("audit_log_fields", audit_log_fields),
        ("scheduled_jobs_fields", scheduled_jobs_fields),
        ("invoice_fields", invoice_fields),
        ("user_fields", user_fields),
        ("connection_fields", connection_fields),
    ]

    @pytest.mark.parametrize("name,fields", ALL_FIELD_DEFS)
    def test_field_tuple_structure(self, name, fields):
        assert len(fields) > 0, f"{name} should not be empty"
        for i, field in enumerate(fields):
            assert len(field) == 5, f"{name}[{i}] should be a 5-tuple, got {len(field)}"
            key, label, fmt, conv, ljust = field
            assert isinstance(key, str), f"{name}[{i}].key should be str"
            assert isinstance(label, str), f"{name}[{i}].label should be str"
            assert isinstance(fmt, str), f"{name}[{i}].fmt should be str"
            assert conv is None or callable(conv), f"{name}[{i}].conv should be None or callable"
            assert isinstance(ljust, bool), f"{name}[{i}].ljust should be bool"
