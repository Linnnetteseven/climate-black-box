"""Tests for Oracle value coercion.

These exist because the same column arrives as three different Python types
depending on the backend, and assuming one of them has broken this codebase
twice.
"""

import json

from services.api.db.coerce import as_json, as_str_list, as_text


class FakeLob:
    """Stands in for an oracledb LOB, which exposes .read()."""

    def __init__(self, text):
        self._text = text

    def read(self):
        return self._text


def test_as_text_handles_lob_str_and_none():
    assert as_text(FakeLob("hello")) == "hello"
    assert as_text("hello") == "hello"
    assert as_text(None) is None


def test_as_json_handles_a_json_string():
    assert as_json('{"a": 1}') == {"a": 1}


def test_as_json_handles_a_lob():
    assert as_json(FakeLob(json.dumps([1, 2]))) == [1, 2]


def test_as_json_passes_through_already_parsed_values():
    """Autonomous Database parses IS JSON columns before we see them."""
    assert as_json({"a": 1}) == {"a": 1}
    assert as_json([1, 2]) == [1, 2]


def test_as_json_returns_the_default_rather_than_raising():
    assert as_json("not json at all", default=[]) == []
    assert as_json(None, default={"x": 1}) == {"x": 1}


def test_as_str_list_handles_comma_separated_text():
    assert as_str_list("cloud_masked, coverage_ok") == ["cloud_masked", "coverage_ok"]


def test_as_str_list_handles_a_json_array():
    assert as_str_list('["a", "b"]') == ["a", "b"]


def test_as_str_list_handles_an_already_parsed_list():
    assert as_str_list(["a", "b"]) == ["a", "b"]


def test_as_str_list_of_nothing_is_empty():
    assert as_str_list(None) == []
    assert as_str_list("") == []
