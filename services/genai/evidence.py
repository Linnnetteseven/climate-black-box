"""Assemble the bounded evidence packet an investigation is allowed to see.

The model never gets the database. It gets this: a small, explicit set of facts
that already exist, each one carrying the id of the record it came from. That
constraint is what makes "cite your evidence" enforceable rather than a polite
request in a prompt -- if a statement references an id that is not in the
packet, we can detect it mechanically.

The packet is capped. A model given fifty observations will summarise fifty
observations; a model given the eight that the alert actually rests on, plus
their rainfall context, has to engage with the specific question.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

#: Hard ceiling on the serialised packet. Chosen so the whole thing stays
#: readable by a human reviewer in one screen -- if we cannot read it, we
#: cannot audit what the model was told.
MAX_PACKET_BYTES = 4096

#: How many observation periods either side of the breach to include.
CONTEXT_PERIODS = 3


@dataclass
class Fact:
    """One citable statement of something already measured."""

    evidence_id: str
    kind: str          # observation | rainfall | quality | reference
    period: str
    statement: str
    value: str | None = None


@dataclass
class EvidencePacket:
    project_id: str
    project_name: str
    alert_id: str
    metric: str
    rule_version: str
    method: str
    observed: str
    expected_band: str
    consecutive_periods: int
    seasonal_note: str
    facts: list[Fact] = field(default_factory=list)

    @property
    def evidence_ids(self) -> list[str]:
        return sorted({f.evidence_id for f in self.facts})

    def to_json(self) -> str:
        payload = asdict(self)
        text = json.dumps(payload, indent=1, sort_keys=True)
        if len(text.encode()) > MAX_PACKET_BYTES:
            # Drop context facts from the outside in rather than truncating the
            # JSON, so what the model sees is always well-formed and complete.
            trimmed = dict(payload)
            while len(json.dumps(trimmed, indent=1, sort_keys=True).encode()) > MAX_PACKET_BYTES:
                if len(trimmed["facts"]) <= 4:
                    break
                trimmed["facts"] = trimmed["facts"][1:-1]
            text = json.dumps(trimmed, indent=1, sort_keys=True)
        return text


def build_packet(
    *,
    project_id: str,
    project_name: str,
    alert: dict[str, Any],
    observations: list[dict[str, Any]],
    seasonal_note: str,
) -> EvidencePacket:
    """Gather only the evidence this alert rests on, plus nearby context."""
    breaching = set(json.loads(alert["evidence_ids"]) if isinstance(alert["evidence_ids"], str)
                    else alert["evidence_ids"])

    ordered = sorted(observations, key=lambda o: o["period_key"])
    indices = [i for i, o in enumerate(ordered) if o["period_key"] in breaching]
    if indices:
        lo = max(0, min(indices) - CONTEXT_PERIODS)
        hi = min(len(ordered), max(indices) + 1 + CONTEXT_PERIODS)
        window = ordered[lo:hi]
    else:
        window = ordered[-(CONTEXT_PERIODS * 2):]

    facts: list[Fact] = []
    for o in window:
        period = o["period_key"]
        in_breach = period in breaching
        if o["value"] is None:
            facts.append(Fact(
                evidence_id=o["id"], kind="quality", period=period,
                statement="No usable observation: every pixel in the project area was "
                          "masked as cloud, shadow or fill.",
            ))
            continue

        facts.append(Fact(
            evidence_id=o["id"], kind="observation", period=period,
            statement=f"Mean NDVI over the project area"
                      f"{' (a period the alert rests on)' if in_breach else ''}.",
            value=f"{float(o['value']):.4f}",
        ))
        coverage = float(o["valid_pixel_fraction"] or 0)
        facts.append(Fact(
            evidence_id=o["id"], kind="quality", period=period,
            statement="Share of pixels inside the project area that survived cloud, "
                      "shadow and saturation masking."
                      + ("" if coverage >= 0.75 else
                         " Below the 0.75 floor, so this period is excluded from alerting."),
            value=f"{coverage:.2f}",
        ))
        if o.get("precipitation_mm") is not None:
            facts.append(Fact(
                evidence_id=o.get("rainfall_id") or f"rain-{period}",
                kind="rainfall", period=period,
                statement="Monthly precipitation from ERA5 reanalysis at roughly 25 km "
                          "resolution. District-scale context only; it cannot resolve "
                          "conditions at this site.",
                value=f"{float(o['precipitation_mm']):.1f} mm",
            ))

    return EvidencePacket(
        project_id=project_id,
        project_name=project_name,
        alert_id=alert["id"],
        metric=alert["metric"],
        rule_version=alert["rule_version"],
        method=alert["method"],
        observed=f"{float(alert['observed_value']):.4f} (seasonally adjusted anomaly)",
        expected_band=f"[{float(alert['expected_low']):.4f}, {float(alert['expected_high']):.4f}]",
        consecutive_periods=int(alert["consecutive_periods"]),
        seasonal_note=seasonal_note,
        facts=facts,
    )
