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
