"""Tests for template engine with !{VAR} syntax."""
import pytest
from backend.app.services.template_engine import (
    extract_variable_names,
    render_template,
    count_variable_references,
)


class TestExtractVariableNames:
    def test_extracts_single_variable(self):
        assert extract_variable_names("Hello !{NAME}") == ["NAME"]

    def test_extracts_multiple_variables(self):
        result = extract_variable_names("!{A} and !{B}")
        assert result == ["A", "B"]

    def test_duplicate_variables_extracted_once(self):
        result = extract_variable_names("!{X} then !{X} again")
        assert result == ["X"]

    def test_no_variables(self):
        assert extract_variable_names("plain text") == []

    def test_old_dollar_syntax_ignored(self):
        assert extract_variable_names("${OLD_VAR}") == []

    def test_underscore_and_digits(self):
        result = extract_variable_names("!{MY_VAR_2}")
        assert result == ["MY_VAR_2"]


class TestRenderTemplate:
    def test_all_resolved(self):
        result = render_template("Hi !{NAME}, project !{PROJ}", {"NAME": "Alice", "PROJ": "X"})
        assert result.content == "Hi Alice, project X"
        assert result.warnings == []

    def test_unresolved_preserved(self):
        result = render_template("Hi !{NAME}", {})
        assert result.content == "Hi !{NAME}"
        assert len(result.warnings) == 1
        assert "!{NAME}" in result.warnings[0]

    def test_partial_resolution(self):
        result = render_template("!{A} and !{B}", {"A": "yes"})
        assert result.content == "yes and !{B}"
        assert len(result.warnings) == 1

    def test_old_dollar_syntax_not_rendered(self):
        result = render_template("${OLD}", {"OLD": "value"})
        assert result.content == "${OLD}"
        assert result.warnings == []


class TestCountVariableReferences:
    def test_counts_occurrences(self):
        assert count_variable_references("!{X} and !{X} and !{Y}", "X") == 2

    def test_zero_occurrences(self):
        assert count_variable_references("no vars here", "X") == 0

    def test_does_not_count_old_syntax(self):
        assert count_variable_references("${X}", "X") == 0
