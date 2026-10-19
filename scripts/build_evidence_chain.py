"""Create the audit chain for a project, and anchor it on CKB.

Runs the alert rule over what is in Oracle, writes the alert, then builds an
append-only chain of audit events -- each manifest carrying the hash of the one
before it -- and anchors each on CKB testnet.

The chain is an application-level structure anchored on CKB. It is not
enforced by an on-chain script, and we say so rather than implying a smart
contract we did not write.

Anchoring degrades honestly: if the signer has no testnet funds the events are
still written with their hashes and the anchor rows are left `pending`. A
pending anchor is displayed as pending. We never show a fabricated transaction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.analytics.alerts import Period, evaluate  # noqa: E402
from services.analytics.seasonal import build_climatology, deseasonalise, describe  # noqa: E402
from services.api.db.connection import cursor  # noqa: E402
from services.ckb.canonical import manifest_hash  # noqa: E402
from services.ckb.manifest import alert_manifest, observation_manifest  # noqa: E402
from services.ckb import ledger_client  # noqa: E402

load_dotenv()
log = logging.getLogger("cbb.chain")

CKB_DIR = Path(__file__).resolve().parents[1] / "services" / "ckb"
BASELINE_BEFORE = "2025"


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}-{hashlib.sha256('|'.join(parts).encode()).hexdigest()[:16]}"


def load_series(project_id: str) -> list[dict]:
    with cursor() as cur:
        cur.execute(
            """SELECT id, period_key, value, valid_pixel_fraction, cloud_cover_pct,
                      observed_at, processing_version, evidence_asset_id, unit
                 FROM observations
                WHERE project_id = :pid AND metric = 'ndvi_mean'
                ORDER BY period_key""",
            pid=project_id,
        )
        rows = [
            dict(id=r[0], period_key=r[1], value=r[2], valid_pixel_fraction=r[3],
                 cloud_cover_pct=r[4], observed_at=r[5], processing_version=r[6],
                 evidence_asset_id=r[7], unit=r[8])
            for r in cur
        ]
    with cursor() as cur:
        cur.execute(
            """SELECT o.id, e.source_dataset, e.source_id
                 FROM observations o JOIN evidence_assets e ON e.id = o.evidence_asset_id
                WHERE o.project_id = :pid""",
            pid=project_id,
        )
        sources = {r[0]: (r[1], r[2]) for r in cur}
    for row in rows:
        row["source_dataset"], row["source_scene_id"] = sources.get(
            row["id"], ("Landsat Collection 2 Level-2 (landsat-c2-l2)", None)
        )
    return rows


def run_rule(rows: list[dict]):
    periods = [
        Period(r["period_key"], i, float(r["value"]) if r["value"] is not None else None,
               float(r["valid_pixel_fraction"] or 0))
        for i, r in enumerate(rows)
    ]
    baseline = [p for p in periods if p.period_id < BASELINE_BEFORE]
    observed = [p for p in periods if p.period_id >= BASELINE_BEFORE]
    clim = build_climatology(baseline)
    decision = evaluate(deseasonalise(baseline, clim), deseasonalise(observed, clim))
    return decision, clim


def persist_alert(project_id: str, decision, clim) -> str | None:
    if not decision.fired:
        log.info("  rule did not fire -- nothing to persist. This is a result, not a failure.")
        return None

    alert_id = _id("alert", project_id, decision.rule_version, decision.breaching_period_ids[-1])
    if ledger_client.project_ledger(project_id):
        # Ledger mode: an alert already on record keeps its status (it may have been resolved)
        with cursor() as cur:
            cur.execute("SELECT status FROM alerts WHERE id = :a", a=alert_id)
            found = cur.fetchone()
        if found:
            log.info("  alert %s already on record (%s), left as is", alert_id, found[0])
            return alert_id
    explanation = " ".join(decision.reasons)
    limitations = (
        "NDVI is a vegetation greenness indicator, not tree survival, canopy cover or "
        "carbon. The comparison is seasonally adjusted against the approved baseline "
        f"window. {describe(clim)} Rainfall context is ERA5 at roughly 25 km and cannot "
        "resolve conditions at this site. No cause is established by this alert."
    )
    with cursor() as cur:
        cur.execute("DELETE FROM investigations WHERE alert_id = :a", a=alert_id)
        cur.execute("DELETE FROM alerts WHERE id = :a", a=alert_id)
        cur.execute(
            """INSERT INTO alerts
                 (id, project_id, metric, rule_version, method, severity, status,
                  observed_value, expected_value, expected_low, expected_high,
                  deviation_abs, deviation_pct, consecutive_periods,
                  quality_flags, evidence_ids, explanation, limitations, simulation_status)
               VALUES (:id, :pid, 'ndvi_mean', :rule, :method, 'review', 'open',
                       :ov, :ev, :lo, :hi, :dabs, :dpct, :n,
                       'coverage_ok,seasonally_adjusted', :eids, :expl, :lim, 'real')""",
            id=alert_id, pid=project_id, rule=decision.rule_version, method=decision.method,
            ov=decision.observed_value, ev=decision.expected_value,
            lo=decision.expected_low, hi=decision.expected_high,
            dabs=decision.deviation_abs, dpct=decision.deviation_pct,
            n=decision.consecutive_periods,
            eids=json.dumps(decision.evidence_ids),
            expl=explanation, lim=limitations,
        )
    log.info("  alert %s persisted (%d consecutive periods)", alert_id, decision.consecutive_periods)
    return alert_id


def anchor(hashes: list[str]) -> dict:
    """Anchor a batch of manifest hashes in one transaction.

    One call, one transaction, one output cell per hash. Anchoring them
    separately fails: each would spend the same unconfirmed input and CKB
    rejects the rest as replace-by-fee conflicts.

    The private key never enters this process -- it is read by the Node signer
    from the environment.
    """
    try:
        result = subprocess.run(
            ["node", "anchor.mjs", *(f"0x{h}" for h in hashes)],
            cwd=CKB_DIR, capture_output=True, text=True, timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "code": "anchor_unavailable", "message": str(exc)}
    if result.returncode != 0:
        try:
            return json.loads(result.stderr.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return {"ok": False, "code": "anchor_failed", "message": result.stderr[:300]}
    return json.loads(result.stdout.strip().splitlines()[-1])


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="mau-transmara-demo")
    ap.add_argument("--no-anchor", action="store_true", help="build the chain but do not touch CKB")
    args = ap.parse_args()

    log.info("project: %s", args.project)
    rows = load_series(args.project)
    log.info("  %d observations", len(rows))

    decision, clim = run_rule(rows)
    alert_id = persist_alert(args.project, decision, clim)

    # The events we anchor: the observations the alert actually rests on, then
    # the alert itself. Not all 45 -- the chain should carry the evidence that
    # matters, and each anchor costs a transaction.
    breaching = set(decision.breaching_period_ids)
    subjects = [r for r in rows if r["period_key"] in breaching] if alert_id else rows[-2:]

    previous_hash: str | None = None
    created = 0
    ledgered = ledger_client.project_ledger(args.project) is not None
    existing: set[str] = set()
    if ledgered:
        # Append-only: once a project has an on-chain ledger its history can't be
        # rebuilt (the ledger's type script would refuse), so only new events are written.
        with cursor() as cur:
            cur.execute("SELECT id, manifest_sha256 FROM audit_events WHERE project_id = :p "
                        "ORDER BY created_at, id", p=args.project)
            rows_existing = cur.fetchall()
        existing = {r[0] for r in rows_existing}
        previous_hash = rows_existing[-1][1] if rows_existing else None
        log.info("  ledger mode: %d events already recorded, appending only new ones", len(existing))
    else:
        with cursor() as cur:
            cur.execute("DELETE FROM chain_anchors WHERE event_id IN "
                        "(SELECT id FROM audit_events WHERE project_id = :p)", p=args.project)
            cur.execute("DELETE FROM audit_events WHERE project_id = :p", p=args.project)

    for row in subjects:
        event_id = _id("evt", args.project, row["id"])
        if event_id in existing:
            continue
        manifest = observation_manifest(
            project_id=args.project, event_id=event_id, observation_id=row["id"],
            metric="ndvi_mean", value=float(row["value"]) if row["value"] is not None else None,
            unit=row["unit"], observed_at=row["observed_at"], period_key=row["period_key"],
            source_dataset=row["source_dataset"], source_scene_id=row["source_scene_id"],
            valid_pixel_fraction=float(row["valid_pixel_fraction"] or 0),
            cloud_cover_pct=float(row["cloud_cover_pct"]) if row["cloud_cover_pct"] is not None else None,
            processing_version=row["processing_version"], simulation_status="real",
            previous_event_hash=previous_hash,
        )
        previous_hash = _write_event(args.project, event_id, "observation_recorded",
                                     "observations", row["id"], manifest)
        created += 1

    if alert_id and _id("evt", args.project, alert_id) not in existing:
        event_id = _id("evt", args.project, alert_id)
        manifest = alert_manifest(
            project_id=args.project, event_id=event_id, alert_id=alert_id,
            metric="ndvi_mean", rule_version=decision.rule_version, method=decision.method,
            observed_value=decision.observed_value, expected_value=decision.expected_value,
            expected_low=decision.expected_low, expected_high=decision.expected_high,
            consecutive_periods=decision.consecutive_periods,
            evidence_ids=decision.evidence_ids, simulation_status="real",
            previous_event_hash=previous_hash,
        )
        previous_hash = _write_event(args.project, event_id, "alert_raised",
                                     "alerts", alert_id, manifest)
        created += 1

    log.info("  %d audit events written, chained", created)

    if args.no_anchor:
        log.info("  --no-anchor: skipping CKB")
        return 0

    if ledgered:
        result = ledger_client.append_pending(args.project)
        if not result.get("ok"):
            log.warning("  ledger append failed (%s): %s", result.get("code"), str(result.get("message"))[:160])
        return 0
    _anchor_pending(args.project)
    return 0


def _write_event(project_id, event_id, event_type, table, subject_id, manifest) -> str:
    digest = manifest_hash(manifest)
    with cursor() as cur:
        cur.execute(
            """INSERT INTO audit_events
                 (id, project_id, event_type, subject_table, subject_id, actor,
                  canonical_manifest, manifest_sha256, previous_event_sha256, simulation_status)
               VALUES (:id, :pid, :etype, :tbl, :sid, 'pipeline',
                       :manifest, :sha, :prev, 'real')""",
            id=event_id, pid=project_id, etype=event_type, tbl=table, sid=subject_id,
            manifest=json.dumps(manifest), sha=digest,
            prev=manifest.get("previous_event_hash"),
        )
    return digest


def _anchor_pending(project_id: str) -> None:
    with cursor() as cur:
        cur.execute(
            """SELECT id, manifest_sha256 FROM audit_events
                WHERE project_id = :p ORDER BY created_at""", p=project_id)
        events = cur.fetchall()

    if not events:
        return

    result = anchor([digest for _, digest in events])

    if not result.get("ok"):
        # Every event is recorded as pending, with nothing invented. A pending
        # anchor is displayed as pending.
        for event_id, digest in events:
            with cursor() as cur:
                cur.execute(
                    """INSERT INTO chain_anchors
                         (id, event_id, network, manifest_sha256, status)
                       VALUES (:id, :ev, 'ckb-testnet', :sha, 'pending')""",
                    id=_id("anc", event_id), ev=event_id, sha=digest,
                )
        log.warning("  NOT anchored (%s): %s", result.get("code"),
                    str(result.get("message"))[:160])
        return

    tx_hash = result["tx_hash"]
    by_hash = {a["manifest_sha256"].lower(): a["output_index"] for a in result["anchors"]}
    for event_id, digest in events:
        index = by_hash[f"0x{digest}".lower()]
        with cursor() as cur:
            cur.execute(
                """INSERT INTO chain_anchors
                     (id, event_id, network, tx_hash, output_index, manifest_sha256,
                      status, explorer_url, anchored_at)
                   VALUES (:id, :ev, 'ckb-testnet', :tx, :idx, :sha, 'confirmed',
                           :url, :ts)""",
                id=_id("anc", event_id), ev=event_id, tx=tx_hash, idx=index,
                sha=digest, url=result["explorer_url"], ts=datetime.now(timezone.utc),
            )
    log.info("  anchored %d events in one transaction: %s", len(events), tx_hash)
    log.info("  %s", result["explorer_url"])


if __name__ == "__main__":
    raise SystemExit(main())
