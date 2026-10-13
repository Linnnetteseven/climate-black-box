"""Golden tests for canonicalisation.

If any of these fail, nothing else in the CKB lane means anything: the
anchored hash would stop matching the manifest it claims to commit to.
"""

import pytest

from services.ckb.canonical import (
    NonCanonicalValue,
    canonical_bytes,
    hashes_match,
    manifest_hash,
)

GOLDEN = {
    "schema_version": "1.0",
    "project_id": "kiambu-restoration-demo",
    "event_id": "evt_000003",
    "event_type": "observation_recorded",
    "observed_at": "2026-08-15T07:42:11Z",
    "observation_ids": ["obs_2026_08"],
    "source_dataset": "Landsat Collection 2 Level-2 (landsat-c2-l2)",
    "source_scene_id": "LC09_L2SP_168061_20260815_20260817_02_T1",
    "asset_sha256": ["9f2c1b"],
    "processing_version": "ndvi-v1",
    "metric_name": "ndvi_mean",
    "metric_value": "0.42",
    "unit": "index",
    "quality_summary": {"valid_pixel_fraction": "0.87", "cloud_cover_scene_pct": "12.4"},
    "previous_event_hash": None,
    "created_at": "2026-10-13T09:00:00Z",
    "simulation_status": "real",
}

#: Pinned so a refactor that changes the bytes fails loudly rather than
#: silently invalidating every anchor already on testnet.
GOLDEN_HASH = "67d38ec37fc012f5bf32b9c7d445d2faf17704e91e0d2c37c5e1fa8e54c63420"


def test_golden_hash_is_pinned():
    """Guards every anchor already written to testnet against a silent
    change in the canonical form."""
    assert manifest_hash(GOLDEN) == GOLDEN_HASH


def test_hash_is_stable_across_runs():
    assert manifest_hash(GOLDEN) == manifest_hash(dict(GOLDEN))


def test_key_order_does_not_change_the_hash():
    shuffled = {k: GOLDEN[k] for k in reversed(list(GOLDEN))}
    assert shuffled != GOLDEN or True  # dict equality ignores order; compare bytes
    assert canonical_bytes(shuffled) == canonical_bytes(GOLDEN)
    assert manifest_hash(shuffled) == manifest_hash(GOLDEN)


def test_nested_key_order_does_not_change_the_hash():
    nested = dict(GOLDEN)
    nested["quality_summary"] = {
        "cloud_cover_scene_pct": "12.4",
        "valid_pixel_fraction": "0.87",
    }
    assert manifest_hash(nested) == manifest_hash(GOLDEN)


def test_changing_any_field_changes_the_hash():
    tampered = dict(GOLDEN, metric_value="0.43")
    assert manifest_hash(tampered) != manifest_hash(GOLDEN)


def test_tampering_inside_a_nested_object_changes_the_hash():
    tampered = dict(GOLDEN)
    tampered["quality_summary"] = dict(GOLDEN["quality_summary"], valid_pixel_fraction="0.99")
    assert manifest_hash(tampered) != manifest_hash(GOLDEN)


def test_list_order_is_significant():
    a = dict(GOLDEN, asset_sha256=["aa", "bb"])
    b = dict(GOLDEN, asset_sha256=["bb", "aa"])
    assert manifest_hash(a) != manifest_hash(b)


def test_null_and_missing_are_different_manifests():
    without = {k: v for k, v in GOLDEN.items() if k != "previous_event_hash"}
    assert manifest_hash(without) != manifest_hash(GOLDEN)


def test_no_insignificant_whitespace():
    raw = canonical_bytes(GOLDEN)
    assert b", " not in raw
    assert b": " not in raw


def test_output_is_utf8_not_escaped():
    raw = canonical_bytes({"note": "Kiambu – ndvi"})
    assert "–".encode("utf-8") in raw


@pytest.mark.parametrize("bad", [0.42, 42, {"nested": 1.0}, ["a", 2]])
def test_numbers_are_rejected(bad):
    with pytest.raises(NonCanonicalValue):
        canonical_bytes({"schema_version": "1.0", "value": bad})


def test_booleans_are_allowed():
    assert manifest_hash({"flag": True}) != manifest_hash({"flag": False})


def test_hashes_match_is_tolerant_of_casing_and_0x():
    h = manifest_hash(GOLDEN)
    assert hashes_match(h, GOLDEN)
    assert hashes_match(h.upper(), GOLDEN)
    assert hashes_match("0x" + h, GOLDEN)
    assert not hashes_match(h, dict(GOLDEN, metric_value="0.99"))
