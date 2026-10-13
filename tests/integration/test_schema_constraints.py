"""Integration tests against a live Oracle database.

These exist because two of our honesty guarantees are enforced in SQL rather
than in Python -- deliberately, because application code is what we will be
editing at 2am. A guarantee nobody tests is a guarantee nobody has.

Skipped automatically when no database is reachable, so `make test-unit`
stays runnable on a laptop with nothing running.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone

import pytest

oracledb = pytest.importorskip("oracledb")


def _connect():
    return oracledb.connect(
        user=os.getenv("ORACLE_APP_USER", "cbb"),
        password=os.environ["ORACLE_APP_PASSWORD"],
        dsn=os.getenv("ORACLE_DSN", "localhost:1521/FREEPDB1"),
    )


@pytest.fixture(scope="module")
def conn():
    if not os.getenv("ORACLE_APP_PASSWORD"):
        pytest.skip("no ORACLE_APP_PASSWORD; set it or run `make up`")
    try:
        connection = _connect()
    except oracledb.DatabaseError as exc:
        pytest.skip(f"no database reachable: {exc}")
    yield connection
    connection.rollback()
    connection.close()


@pytest.fixture
def project(conn):
    """A throwaway project, rolled back after each test."""
    pid = f"test-{uuid.uuid4().hex[:8]}"
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO projects (id, name, country, status, simulation_status)
               VALUES (:id, 'Test project', 'Kenya', 'active', 'simulated')""",
            id=pid,
        )
    yield pid
    conn.rollback()


def test_schema_has_every_expected_table(conn):
    expected = {
        "PROJECTS", "COMMITMENTS", "EVIDENCE_ASSETS", "OBSERVATIONS", "ALERTS",
        "INVESTIGATIONS", "INTERVENTIONS", "AUDIT_EVENTS", "CHAIN_ANCHORS",
    }
    with conn.cursor() as cur:
        cur.execute("SELECT table_name FROM user_tables")
        actual = {row[0] for row in cur}
    assert expected <= actual, f"missing: {expected - actual}"


def test_views_exist(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT view_name FROM user_views")
        views = {row[0] for row in cur}
    assert {"V_PROJECT_OBSERVATIONS", "V_PROJECT_ALERTS", "V_AUDIT_TIMELINE"} <= views


# --- the guarantees ---------------------------------------------------------

def test_an_intervention_cannot_claim_to_be_real(conn, project):
    """We have no field team. The database refuses the lie outright."""
    with conn.cursor() as cur, pytest.raises(oracledb.DatabaseError) as exc:
        cur.execute(
            """INSERT INTO interventions
                 (id, project_id, action, actor, action_date, simulation_status)
               VALUES (:id, :pid, 'Replanting', 'A. Person', :d, 'real')""",
            id=uuid.uuid4().hex[:16], pid=project, d=date(2026, 9, 1),
        )
    assert "CK_INTERVENTIONS_SIMULATED" in str(exc.value).upper()


def test_a_simulated_intervention_is_accepted(conn, project):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO interventions
                 (id, project_id, action, actor, action_date, simulation_status)
               VALUES (:id, :pid, 'Replanting', 'A. Person', :d, 'simulated')""",
            id=uuid.uuid4().hex[:16], pid=project, d=date(2026, 9, 1),
        )
        cur.execute("SELECT COUNT(*) FROM interventions WHERE project_id = :p", p=project)
        assert cur.fetchone()[0] == 1


def test_a_confirmed_anchor_without_a_tx_hash_is_rejected(conn, project):
    """A 'confirmed' anchor with no transaction would be a lie on stage."""
    event_id = uuid.uuid4().hex[:16]
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO audit_events
                 (id, project_id, event_type, manifest_sha256, simulation_status)
               VALUES (:id, :pid, 'observation_recorded', :h, 'real')""",
            id=event_id, pid=project, h=uuid.uuid4().hex * 2,
        )
        with pytest.raises(oracledb.DatabaseError) as exc:
            cur.execute(
                """INSERT INTO chain_anchors
                     (id, event_id, network, manifest_sha256, status)
                   VALUES (:id, :ev, 'ckb-testnet', :h, 'confirmed')""",
                id=uuid.uuid4().hex[:16], ev=event_id, h=uuid.uuid4().hex * 2,
            )
    assert "CK_ANCHORS_CONFIRMED" in str(exc.value).upper()


def test_an_approved_commitment_must_name_its_reviewer(conn, project):
    """No anonymous baselines: who approved it is part of the evidence."""
    with conn.cursor() as cur, pytest.raises(oracledb.DatabaseError) as exc:
        cur.execute(
            """INSERT INTO commitments
                 (id, project_id, metric, extraction_status, simulation_status)
               VALUES (:id, :pid, 'ndvi_mean', 'approved', 'simulated')""",
            id=uuid.uuid4().hex[:16], pid=project,
        )
    assert "CK_COMMITMENTS_REVIEWED" in str(exc.value).upper()


def test_simulation_status_rejects_an_unknown_value(conn, project):
    with conn.cursor() as cur, pytest.raises(oracledb.DatabaseError):
        cur.execute(
            """INSERT INTO evidence_assets
                 (id, project_id, source_type, source_dataset, simulation_status)
               VALUES (:id, :pid, 'satellite', 'Landsat', 'probably_fine')""",
            id=uuid.uuid4().hex[:16], pid=project,
        )


def test_observations_are_unique_per_period(conn, project):
    """Re-running the loader must not duplicate history."""
    args = dict(pid=project, ps=datetime(2026, 8, 1, tzinfo=timezone.utc),
                pe=datetime(2026, 8, 31, tzinfo=timezone.utc))
    sql = """INSERT INTO observations
               (id, project_id, metric, value, unit, period_key, period_start,
                period_end, processing_version, simulation_status)
             VALUES (:id, :pid, 'ndvi_mean', 0.42, 'index', '2026-08', :ps, :pe,
                     'ndvi-v1', 'real')"""
    with conn.cursor() as cur:
        cur.execute(sql, id=uuid.uuid4().hex[:16], **args)
        with pytest.raises(oracledb.DatabaseError) as exc:
            cur.execute(sql, id=uuid.uuid4().hex[:16], **args)
    assert "UQ_OBS_PERIOD" in str(exc.value).upper()


def test_valid_pixel_fraction_must_be_a_fraction(conn, project):
    with conn.cursor() as cur, pytest.raises(oracledb.DatabaseError):
        cur.execute(
            """INSERT INTO observations
                 (id, project_id, metric, value, unit, period_key, period_start,
                  period_end, valid_pixel_fraction, processing_version, simulation_status)
               VALUES (:id, :pid, 'ndvi_mean', 0.42, 'index', '2026-09', :ps, :pe,
                       87, 'ndvi-v1', 'real')""",
            id=uuid.uuid4().hex[:16], pid=project,
            ps=datetime(2026, 9, 1, tzinfo=timezone.utc),
            pe=datetime(2026, 9, 30, tzinfo=timezone.utc),
        )
