"""Turn an evidence packet into an investigation: a summary and hypotheses.

Two implementations, one contract.

`deterministic_investigation` reads the packet and writes the summary from
rules. It is the fallback, it needs no credentials, and it is what ships if OCI
Generative AI is unreachable. Output is badged `fallback` so nobody can mistake
it for model output.

`model_investigation` asks OCI Generative AI the same question, then validates
the answer hard: the schema must match, and **every evidence id cited must
exist in the packet we supplied**. A model that invents an id, or invents a
measurement, fails validation and we fall back. That check is the whole reason
the evidence packet is a closed set.

Neither implementation is allowed to assert a cause. The output is hypotheses
plus what evidence would distinguish them, because that is what an investigator
can act on and a causal claim from this data would not be defensible.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from services.genai.evidence import EvidencePacket

log = logging.getLogger("cbb.genai")

PROMPT_VERSION = "investigate-v1"


@dataclass
class Hypothesis:
    statement: str
    evidence_ids: list[str]
    confidence: str  # low | medium | high


@dataclass
class Investigation:
    summary: str
    hypotheses: list[Hypothesis]
    evidence_ids: list[str]
    missing_evidence: str
    model_id: str | None
    prompt_version: str
    simulation_status: str   # 'real' for model output, 'fallback' for the template


class InvalidModelOutput(ValueError):
    """The model's answer did not satisfy the contract."""


def _coverage_facts(packet: EvidencePacket):
    low, good = [], []
    for fact in packet.facts:
        if fact.kind == "quality" and fact.value is not None:
            (good if float(fact.value) >= 0.75 else low).append(fact)
    return low, good


def _rainfall_trend(packet: EvidencePacket) -> tuple[float | None, list[str]]:
    rain = [(f.period, float(f.value.split()[0]), f.evidence_id)
            for f in packet.facts if f.kind == "rainfall" and f.value]
    if len(rain) < 4:
        return None, [r[2] for r in rain]
    rain.sort()
    half = len(rain) // 2
    earlier = sum(r[1] for r in rain[:half]) / half
    later = sum(r[1] for r in rain[half:]) / (len(rain) - half)
    return later - earlier, [r[2] for r in rain]


def deterministic_investigation(packet: EvidencePacket) -> Investigation:
    """Write the investigation from the packet, by rule. No model involved."""
    low_coverage, good_coverage = _coverage_facts(packet)
    rain_delta, rain_ids = _rainfall_trend(packet)
    obs_ids = [f.evidence_id for f in packet.facts if f.kind == "observation"]

    summary = (
        f"{packet.metric} over {packet.project_name} sat at {packet.observed}, below the "
        f"expected band {packet.expected_band}, for {packet.consecutive_periods} consecutive "
        f"periods. {packet.seasonal_note} "
        f"{len(good_coverage)} of the periods in this window met the 0.75 valid-pixel floor, "
        f"so the signal is not an artefact of cloud cover."
    )

    hypotheses: list[Hypothesis] = []

    if rain_delta is not None and rain_delta < -20:
        hypotheses.append(Hypothesis(
            statement=(
                f"Reduced rainfall. District-scale precipitation fell by roughly "
                f"{abs(rain_delta):.0f} mm per month across this window, which is "
                f"consistent with lower greenness without any change on the ground."
            ),
            evidence_ids=sorted(rain_ids), confidence="medium",
        ))
    else:
        hypotheses.append(Hypothesis(
            statement=(
                "Rainfall does not explain it. District-scale precipitation across this "
                "window is not markedly lower than the surrounding periods, so drought at "
                "that scale is not an obvious cause."
            ),
            evidence_ids=sorted(rain_ids), confidence="medium",
        ))

    hypotheses.append(Hypothesis(
        statement=(
            "Vegetation loss on the ground — clearance, grazing pressure, fire or "
            "harvesting. This is consistent with a sustained decline that persists across "
            "periods with good pixel coverage, but nothing in this evidence distinguishes "
            "between those causes."
        ),
        evidence_ids=sorted(obs_ids), confidence="medium",
    ))

    if low_coverage:
        hypotheses.append(Hypothesis(
            statement=(
                f"Partial measurement bias. {len(low_coverage)} period(s) in this window "
                f"fell below the valid-pixel floor and were excluded. The surviving pixels "
                f"may not represent the whole project area evenly."
            ),
            evidence_ids=sorted({f.evidence_id for f in low_coverage}), confidence="low",
        ))

    missing = (
        "Field observation at the site would separate clearance from drought stress. "
        "Higher-resolution imagery would show whether the decline is uniform across the "
        "polygon or concentrated at its edges. A rain gauge at the site would replace "
        "the 25 km ERA5 grid cell used here, which cannot resolve this area."
    )

    # A hypothesis citing nothing is an opinion, and this system does not
    # publish opinions. Drop it rather than show an uncited claim.
    hypotheses = [h for h in hypotheses if h.evidence_ids]

    return Investigation(
        summary=summary,
        hypotheses=hypotheses,
        evidence_ids=packet.evidence_ids,
        missing_evidence=missing,
        model_id=None,
        prompt_version=PROMPT_VERSION,
        simulation_status="fallback",
    )


SYSTEM_PROMPT = """You are assisting an environmental monitoring review.

You will be given a JSON evidence packet describing one alert and the measurements it rests on. Follow these rules exactly:

1. Use ONLY facts present in the packet. Never state a measurement that is not there.
2. Every hypothesis must cite evidence_id values that appear in the packet.
3. Never assert a cause. Offer hypotheses, and say what further evidence would distinguish them.
4. NDVI is a vegetation greenness indicator. It is not tree survival, canopy cover, biomass or carbon. Do not imply otherwise.
5. Rainfall here is ERA5 at roughly 25 km and cannot resolve a single site.

Return STRICT JSON with this shape and nothing else:
{"summary": "...", "hypotheses": [{"statement": "...", "evidence_ids": ["..."], "confidence": "low|medium|high"}], "missing_evidence": "..."}"""


def _validate(payload: dict, packet: EvidencePacket, model_id: str) -> Investigation:
    allowed = set(packet.evidence_ids)
    if not isinstance(payload.get("summary"), str) or not payload["summary"].strip():
        raise InvalidModelOutput("missing summary")
    raw = payload.get("hypotheses")
    if not isinstance(raw, list) or not raw:
        raise InvalidModelOutput("missing hypotheses")

    hypotheses: list[Hypothesis] = []
    for item in raw:
        ids = item.get("evidence_ids") or []
        if not isinstance(ids, list) or not ids:
            raise InvalidModelOutput("a hypothesis cited no evidence")
        unknown = set(ids) - allowed
        if unknown:
            # The decisive check: the model referenced something we never gave it.
            raise InvalidModelOutput(f"hypothesis cited unknown evidence ids: {sorted(unknown)}")
        if item.get("confidence") not in {"low", "medium", "high"}:
            raise InvalidModelOutput("bad confidence value")
        if not isinstance(item.get("statement"), str) or not item["statement"].strip():
            raise InvalidModelOutput("empty hypothesis statement")
        hypotheses.append(Hypothesis(item["statement"].strip(), sorted(ids), item["confidence"]))

    # Guard the claims we promised never to make, whatever the prompt said.
    body = payload["summary"] + " ".join(h.statement for h in hypotheses)
    for forbidden in (r"\bcarbon\b", r"\bproves?\b", r"\bproven\b", r"\bcertainly\b"):
        if re.search(forbidden, body, re.IGNORECASE):
            raise InvalidModelOutput(f"output made a claim we do not permit: {forbidden}")

    return Investigation(
        summary=payload["summary"].strip(),
        hypotheses=hypotheses,
        evidence_ids=packet.evidence_ids,
        missing_evidence=str(payload.get("missing_evidence") or "").strip()
                         or "Not stated by the model.",
        model_id=model_id,
        prompt_version=PROMPT_VERSION,
        simulation_status="real",
    )


def investigate(packet: EvidencePacket) -> Investigation:
    """Model output when it is available and valid; the template otherwise."""
    if os.getenv("OCI_GENAI_ENABLED", "false").lower() != "true":
        log.info("OCI GenAI disabled; using deterministic investigation")
        return deterministic_investigation(packet)

    try:
        from services.genai.oci_client import complete_json  # imported lazily
        payload, model_id = complete_json(SYSTEM_PROMPT, packet.to_json())
        return _validate(payload, packet, model_id)
    except Exception as exc:
        # Any failure -- unreachable, malformed, or caught inventing evidence --
        # falls back rather than showing something we cannot stand behind.
        log.warning("GenAI investigation rejected (%s); falling back", exc)
        return deterministic_investigation(packet)
