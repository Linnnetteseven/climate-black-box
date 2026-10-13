"""Tests for the investigation layer.

The property that matters most: a model cannot smuggle in a measurement or an
evidence id we never gave it. That is enforced by validation, not by the
prompt, so it is tested like a security boundary rather than a style guide.
"""

import pytest

from services.genai.evidence import EvidencePacket, Fact, MAX_PACKET_BYTES, build_packet
from services.genai.investigate import (
    InvalidModelOutput,
    _validate,
    deterministic_investigation,
)


def packet(**over) -> EvidencePacket:
    base = dict(
        project_id="mau-transmara-demo",
        project_name="Transmara Forest Block",
        alert_id="alert-1", metric="ndvi_mean", rule_version="divergence-v1",
        method="robust linear baseline, residual sigma band, 2 consecutive periods",
        observed="-0.1183 (seasonally adjusted anomaly)",
        expected_band="[0.0273, 0.1601]", consecutive_periods=5,
        seasonal_note="Seasonally adjusted against the approved baseline window.",
        facts=[
            Fact("obs-1", "observation", "2026-05", "Mean NDVI.", "0.5954"),
            Fact("obs-1", "quality", "2026-05", "Valid pixels.", "1.00"),
            Fact("rain-2026-05", "rainfall", "2026-05", "ERA5 precipitation.", "87.2 mm"),
            Fact("obs-2", "observation", "2026-09", "Mean NDVI.", "0.4668"),
            Fact("obs-2", "quality", "2026-09", "Valid pixels.", "0.95"),
            Fact("rain-2026-09", "rainfall", "2026-09", "ERA5 precipitation.", "39.8 mm"),
        ],
    )
    base.update(over)
    return EvidencePacket(**base)


# --- the deterministic fallback -------------------------------------------

def test_fallback_is_badged_as_fallback():
    out = deterministic_investigation(packet())
    assert out.simulation_status == "fallback"
    assert out.model_id is None


def test_fallback_cites_only_supplied_evidence():
    p = packet()
    out = deterministic_investigation(p)
    allowed = set(p.evidence_ids)
    for h in out.hypotheses:
        assert h.evidence_ids, "every hypothesis must cite something"
        assert set(h.evidence_ids) <= allowed


def test_fallback_offers_several_hypotheses_and_says_what_is_missing():
    out = deterministic_investigation(packet())
    assert len(out.hypotheses) >= 2
    assert "field observation" in out.missing_evidence.lower()


def test_fallback_never_claims_a_cause_or_mentions_carbon():
    out = deterministic_investigation(packet())
    body = (out.summary + " " + " ".join(h.statement for h in out.hypotheses)).lower()
    for forbidden in ("proves", "proven", "carbon", "caused by"):
        assert forbidden not in body


def test_fallback_flags_low_coverage_as_a_separate_hypothesis():
    p = packet(facts=packet().facts + [Fact("obs-3", "quality", "2026-08", "Valid pixels.", "0.20")])
    out = deterministic_investigation(p)
    assert any("measurement bias" in h.statement.lower() for h in out.hypotheses)


def test_fallback_notices_falling_rainfall():
    p = packet(facts=[
        Fact("rain-1", "rainfall", "2026-01", "ERA5.", "180.0 mm"),
        Fact("rain-2", "rainfall", "2026-02", "ERA5.", "170.0 mm"),
        Fact("rain-3", "rainfall", "2026-03", "ERA5.", "40.0 mm"),
        Fact("rain-4", "rainfall", "2026-04", "ERA5.", "30.0 mm"),
    ])
    out = deterministic_investigation(p)
    assert any("reduced rainfall" in h.statement.lower() for h in out.hypotheses)


# --- validation of model output -------------------------------------------

GOOD = {
    "summary": "Greenness sat below the expected band for five consecutive periods.",
    "hypotheses": [
        {"statement": "Vegetation loss on the ground.",
         "evidence_ids": ["obs-1", "obs-2"], "confidence": "medium"},
    ],
    "missing_evidence": "Field observation would distinguish these.",
}


def test_valid_model_output_is_accepted_and_badged_real():
    out = _validate(dict(GOOD), packet(), "cohere.command-r")
    assert out.simulation_status == "real"
    assert out.model_id == "cohere.command-r"


def test_model_citing_an_unknown_evidence_id_is_rejected():
    """The decisive check: the model referenced something we never supplied."""
    bad = {**GOOD, "hypotheses": [
        {"statement": "Clearance.", "evidence_ids": ["obs-999"], "confidence": "high"}]}
    with pytest.raises(InvalidModelOutput, match="unknown evidence"):
        _validate(bad, packet(), "m")


def test_model_citing_nothing_is_rejected():
    bad = {**GOOD, "hypotheses": [
        {"statement": "Something happened.", "evidence_ids": [], "confidence": "high"}]}
    with pytest.raises(InvalidModelOutput):
        _validate(bad, packet(), "m")


@pytest.mark.parametrize("claim", [
    "This proves the forest was cleared.",
    "The decline certainly reflects carbon loss.",
])
def test_model_making_a_forbidden_claim_is_rejected(claim):
    bad = {**GOOD, "summary": claim}
    with pytest.raises(InvalidModelOutput, match="do not permit"):
        _validate(bad, packet(), "m")


def test_model_with_bad_confidence_is_rejected():
    bad = {**GOOD, "hypotheses": [
        {"statement": "x", "evidence_ids": ["obs-1"], "confidence": "very sure"}]}
    with pytest.raises(InvalidModelOutput):
        _validate(bad, packet(), "m")


def test_empty_summary_is_rejected():
    with pytest.raises(InvalidModelOutput):
        _validate({**GOOD, "summary": "   "}, packet(), "m")


# --- the packet itself -----------------------------------------------------

def test_packet_stays_within_its_size_cap():
    big = packet(facts=[
        Fact(f"obs-{i}", "observation", f"2026-{i:02d}", "Mean NDVI over the area." * 6, "0.5")
        for i in range(1, 60)
    ])
    assert len(big.to_json().encode()) <= MAX_PACKET_BYTES


def test_packet_json_stays_well_formed_when_trimmed():
    import json
    big = packet(facts=[
        Fact(f"obs-{i}", "observation", f"2026-{i:02d}", "x" * 200, "0.5") for i in range(60)
    ])
    json.loads(big.to_json())


def test_build_packet_includes_context_either_side_of_the_breach():
    observations = [
        {"id": f"obs-{i}", "period_key": f"2026-{i:02d}", "value": 0.5,
         "valid_pixel_fraction": 0.9, "precipitation_mm": 40.0}
        for i in range(1, 11)
    ]
    alert = {"id": "a", "metric": "ndvi_mean", "rule_version": "v1", "method": "m",
             "observed_value": -0.1, "expected_low": 0.0, "expected_high": 0.2,
             "consecutive_periods": 2, "evidence_ids": ["2026-07", "2026-08"]}
    p = build_packet(project_id="p", project_name="n", alert=alert,
                     observations=observations, seasonal_note="s")
    periods = {f.period for f in p.facts}
    assert "2026-07" in periods and "2026-08" in periods
    assert "2026-05" in periods  # context before
    assert "2026-10" in periods  # context after
