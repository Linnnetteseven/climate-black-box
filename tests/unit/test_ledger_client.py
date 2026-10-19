"""The mapping from audit events to on-chain ledger entries (no database, no chain)."""

import pytest

from services.api.schemas.contracts import VerificationState
from services.ckb import ledger_client


def test_every_audit_event_type_has_a_ledger_kind():
    allowed = {"observation_recorded", "commitment_approved", "alert_raised", "alert_resolved",
               "investigation_recorded", "intervention_logged", "remeasurement_recorded"}
    assert set(ledger_client.KIND_OF_EVENT) == allowed


def test_observation_entry_uses_its_own_period():
    e = ledger_client.entry_for("observation_recorded", {"period_key": "2025-03"}, "ab" * 32)
    assert e == {"kind": 1, "period": "2025-03", "sha256": "ab" * 32}


def test_alert_entry_uses_the_last_month_it_rests_on():
    e = ledger_client.entry_for("alert_raised", {"created_at": "2026-10-19T10:00:00Z"}, "0x" + "cd" * 32, "2025-07")
    assert e["kind"] == 2 and e["period"] == "2025-07" and not e["sha256"].startswith("0x")


def test_other_events_are_filed_under_their_recording_month():
    e = ledger_client.entry_for("intervention_logged", {"created_at": "2026-02-01T08:00:00Z"}, "ef" * 32)
    assert e["kind"] == 4 and e["period"] == "2026-02"


def test_unknown_event_type_is_refused():
    with pytest.raises(ValueError):
        ledger_client.entry_for("made_up", {}, "00" * 32)


def test_out_of_sequence_is_a_distinct_verification_state():
    assert VerificationState("out_of_sequence") is VerificationState.OUT_OF_SEQUENCE


def test_json_columns_are_read_however_oracle_returns_them():
    assert ledger_client._json_list(["a", "b"]) == ["a", "b"]
    assert ledger_client._json_list('["a"]') == ["a"]
    assert ledger_client._json_list(None) == []


class _FakeCursor:
    def __init__(self, evidence):
        self.evidence, self.calls = evidence, 0

    def execute(self, *_a, **_k):
        self.calls += 1

    def fetchone(self):
        return (self.evidence,) if self.calls == 1 else ("2025-02",)


def test_alert_period_from_the_months_the_rule_recorded():
    assert ledger_client._alert_period(_FakeCursor(["2026-05", "2026-09", "2026-07"]), "a") == "2026-09"


def test_alert_period_falls_back_to_observation_ids():
    assert ledger_client._alert_period(_FakeCursor(["obs-1", "obs-2"]), "a") == "2025-02"
