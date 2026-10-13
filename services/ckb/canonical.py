"""Deterministic serialisation of evidence manifests, and their hashes.

The whole CKB integrity story rests on one property: the same manifest must
produce the same bytes, and therefore the same hash, on every machine, in
every language, on every run. Anything that can vary between runs -- key
order, whitespace, float formatting, unicode normalisation -- is a silent
verification failure waiting to happen months later.

So the rules are deliberately strict and deliberately boring:

* Object keys are sorted by their UTF-8 code points.
* No insignificant whitespace. Separators are exactly ``,`` and ``:``.
* Output is UTF-8, never ASCII-escaped, so the bytes match what other
  languages produce for the same string.
* Numbers are rejected. Numeric values must already be strings in the
  manifest -- see ``docs/ckb-integrity.md``. ``0.42``, ``0.420`` and
  ``4.2e-1`` are the same number but different bytes, and no two languages
  agree on how to render a float. Strings remove the whole class of bug.
* ``None`` is allowed and encodes as ``null``. Omitting a key and setting it
  to null are different manifests, by design.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

#: Bumped only when the canonical form itself changes. A manifest hashed
#: under one version cannot be verified under another.
CANONICALIZATION_VERSION = "cbb-canon-1"


class NonCanonicalValue(ValueError):
    """A value cannot be represented deterministically."""


def _check(value: Any, path: str = "$") -> None:
    """Reject anything whose serialisation is not byte-stable.

    Raising here, loudly, at build time is the entire point: a manifest that
    cannot be canonicalised must never reach the chain.
    """
    if value is None or isinstance(value, str):
        return
    if isinstance(value, bool):
        # bool is a subclass of int, so it must be tested first. True/False
        # render as `true`/`false` identically everywhere, so they are safe.
        return
    if isinstance(value, (int, float)):
        raise NonCanonicalValue(
            f"{path}: numeric value {value!r} must be a string in a manifest. "
            "Float and integer formatting is not portable; see "
            "docs/ckb-integrity.md."
        )
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise NonCanonicalValue(f"{path}: object keys must be strings, got {key!r}")
            _check(value[key], f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _check(item, f"{path}[{index}]")
        return
    raise NonCanonicalValue(f"{path}: unsupported type {type(value).__name__}")


def canonical_bytes(manifest: dict[str, Any]) -> bytes:
    """Return the canonical UTF-8 encoding of ``manifest``.

    Lists keep their order -- order is part of the data. Only object keys are
    sorted, and sorting is applied at every depth.
    """
    if not isinstance(manifest, dict):
        raise NonCanonicalValue("a manifest must be a JSON object at the top level")
    _check(manifest)
    text = json.dumps(
        manifest,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return text.encode("utf-8")


def manifest_hash(manifest: dict[str, Any]) -> str:
    """Return the lowercase hex sha256 of the manifest's canonical bytes.

    This is the value anchored on CKB and the value recomputed at verify time.
    """
    return hashlib.sha256(canonical_bytes(manifest)).hexdigest()


def hashes_match(expected_hex: str, manifest: dict[str, Any]) -> bool:
    """Compare a stored hash against a freshly computed one.

    Case-insensitive on the hex, because explorers and SDKs disagree about
    casing, and tolerant of a leading ``0x`` for the same reason.
    """
    actual = manifest_hash(manifest)
    expected = expected_hex.lower().removeprefix("0x").strip()
    return actual == expected
