"""Normalising what Oracle hands back.

The same column comes back as three different Python types depending on where
you are: a LOB on the local 23ai Free container, a `str` in some driver modes,
and -- for a column with an `IS JSON` constraint on Autonomous Database -- an
already-parsed `dict` or `list`.

Code that assumes one of those breaks when it meets another, which has now
happened twice in this codebase. So the coercion lives in one place and every
reader goes through it.
"""

from __future__ import annotations

import json
from typing import Any


def as_text(value: Any) -> str | None:
    """A LOB, a str, or None -> str or None."""
    if value is None:
        return None
    if hasattr(value, "read"):
        return value.read()
    return value if isinstance(value, str) else str(value)


def as_json(value: Any, default: Any = None) -> Any:
    """A LOB, a JSON str, or an already-parsed dict/list -> the parsed value.

    ADB parses `IS JSON` columns for us; the local container does not. Both are
    accepted, and anything unparseable returns ``default`` rather than raising
    in a request handler.
    """
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    text = as_text(value)
    if not text:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def as_str_list(value: Any) -> list[str]:
    """Comma-separated text or a JSON array -> list of non-empty strings."""
    parsed = as_json(value)
    if isinstance(parsed, list):
        return [str(v) for v in parsed]
    text = as_text(value)
    return [part.strip() for part in text.split(",") if part.strip()] if text else []
