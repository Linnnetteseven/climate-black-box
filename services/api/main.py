"""Climate Black Box API.

The single business-logic boundary. The browser talks to this and nothing
else: not to Oracle, not to CKB. That is what keeps the signing key and the
database credentials server-side, and it is why there is exactly one place
where an answer can be assembled wrongly.

Every route degrades rather than crashes. If Oracle is unreachable the
response says so in a shape the frontend can render as a labelled offline
state, because a blank screen during a demo is worse than an honest one.
"""

from __future__ import annotations

import logging
import os
import uuid
from hmac import compare_digest
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.api.interventions import create_intervention, list_interventions, trend_for
from services.ckb.verifier import verify_event
from services.genai.service import investigation_for
from services.api.db import repository
from services.api.db.connection import DatabaseUnavailable, describe_backend
from services.api.schemas.contracts import (
    Alert,
    Intervention,
    InterventionCreate,
    AuditEvent,
    Commitment,
    ErrorResponse,
    Observation,
    Project,
)

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("cbb.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("starting against %s", describe_backend())
    yield


app = FastAPI(
    title="Climate Black Box API",
    version="0.1.0",
    summary="Evidence, divergence and integrity for climate project monitoring.",
    lifespan=lifespan,
)

# The frontend is served from a different origin in development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("WEB_ORIGIN", "http://localhost:3000")],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    """Every response carries an id, so a UI error can be traced to a log line."""
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


def _error(request: Request, code: str, message: str, status: int) -> JSONResponse:
    body = ErrorResponse(
        code=code,
        message=message,
        request_id=getattr(request.state, "request_id", "unknown"),
    )
    return JSONResponse(status_code=status, content=body.model_dump())


@app.exception_handler(DatabaseUnavailable)
async def _db_unavailable(request: Request, exc: DatabaseUnavailable):
    # Logged in full; the client gets a stable code and no internals.
    log.error("database unavailable: %s", exc)
    return _error(
        request,
        code="database_unavailable",
        message="The evidence store is not reachable. Displayed data may be incomplete.",
        status=503,
    )


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    log.exception("unhandled error")
    return _error(request, "internal_error", "Something went wrong.", 500)


api = APIRouter(prefix="/api")


@api.get("/health", tags=["meta"])
def health() -> dict:
    """Backend identity and reachability.

    `backend` is deliberately explicit so nobody can mistake the local
    container for Autonomous Database when reading a screenshot.
    """
    status = "ok"
    detail = None
    try:
        repository.list_projects()
    except DatabaseUnavailable as exc:
        status, detail = "degraded", str(exc)[:200]
    return {
        "status": status,
        "backend": describe_backend(),
        "detail": detail,
        "checked_at": datetime.now().astimezone().isoformat(),
    }


@api.get("/projects", response_model=list[Project], tags=["projects"])
def get_projects() -> list[Project]:
    return repository.list_projects()


@api.get("/projects/{project_id}", response_model=Project, tags=["projects"])
def get_project(project_id: str, request: Request):
    project = repository.get_project(project_id)
    if project is None:
        return _error(request, "not_found", f"No project with id {project_id!r}.", 404)
    return project


@api.get("/projects/{project_id}/commitments", response_model=list[Commitment], tags=["projects"])
def get_commitments(project_id: str) -> list[Commitment]:
    return repository.list_commitments(project_id)


@api.get("/projects/{project_id}/observations", response_model=list[Observation], tags=["evidence"])
def get_observations(
    project_id: str,
    metric: str | None = Query(default=None, description="e.g. ndvi_mean"),
    frm: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
) -> list[Observation]:
    return repository.list_observations(project_id, metric=metric, frm=frm, to=to)


@api.get("/projects/{project_id}/audit", response_model=list[AuditEvent], tags=["evidence"])
def get_audit(project_id: str) -> list[AuditEvent]:
    return repository.list_audit_events(project_id)


@api.get("/alerts", response_model=list[Alert], tags=["alerts"])
def get_alerts(project_id: str | None = Query(default=None)) -> list[Alert]:
    return repository.list_alerts(project_id)


@api.get("/projects/{project_id}/latest-alert", tags=["alerts"])
def get_latest_alert(project_id: str):
    """The alert the demo opens on, or an explicit null.

    A project with no alert is a result, not an error: it means the detector
    looked and found nothing, which is exactly what the control site shows.
    """
    alert = repository.latest_alert(project_id)
    return {"alert": alert, "detector_ran": True,
            "note": None if alert else
                    "No divergence detected. The rule ran and stayed quiet."}


@api.get("/alerts/{alert_id}", response_model=Alert, tags=["alerts"])
def get_alert(alert_id: str, request: Request):
    alert = repository.get_alert(alert_id)
    if alert is None:
        return _error(request, "not_found", f"No alert with id {alert_id!r}.", 404)
    return alert


@api.get("/projects/{project_id}/interventions", response_model=list[Intervention],
         tags=["interventions"])
def get_interventions(project_id: str) -> list[Intervention]:
    return list_interventions(project_id)


@api.post("/interventions", response_model=Intervention, tags=["interventions"])
def post_intervention(payload: InterventionCreate):
    """Record a corrective action.

    Always stored as `simulated` -- the database refuses anything else, because
    this demonstration has no field team and must not be able to imply it does.
    Logging one appends to the evidence chain.
    """
    return create_intervention(payload)


@api.get("/projects/{project_id}/trend", tags=["interventions"])
def get_trend(project_id: str):
    """Pre/post comparison around the latest intervention, and what to do next."""
    return trend_for(project_id)


@api.get("/alerts/{alert_id}/investigation", tags=["alerts"])
def get_investigation(
    alert_id: str,
    request: Request,
    refresh: bool = Query(default=False),
):
    """Evidence-grounded investigation for an alert.

    `simulation_status` tells you where it came from: `real` means the model
    produced it and the output passed validation; `fallback` means the
    deterministic template did, because the model was unavailable or its answer
    cited evidence we never supplied.
    """
    # Regenerating calls the model, which costs money on the tenancy that owns
    # the key. Reading the stored investigation is free and is what every
    # visitor needs; only a caller holding the shared key may force a new one.
    # Without this, a public URL is a public spend button.
    #
    # The key travels in a header, not the query string: nginx writes full
    # request lines to its access log, and a secret in a URL also survives in
    # browser history and referrers.
    if refresh:
        expected = os.getenv("API_SHARED_KEY")
        presented = request.headers.get("x-api-key")
        if not expected or not presented or not compare_digest(presented, expected):
            refresh = False

    result = investigation_for(alert_id, refresh=refresh)
    if result is None:
        return _error(request, "not_found", f"No alert {alert_id!r}.", 404)
    return result


@api.get("/evidence/{event_id}/verify", tags=["integrity"])
def get_verify(event_id: str, request: Request):
    """Re-hash the stored manifest and compare with the on-chain commitment."""
    result = verify_event(event_id)
    if result is None:
        return _error(request, "not_found", f"No audit event {event_id!r}.", 404)
    return result


@api.post("/evidence/{event_id}/tamper-check", tags=["integrity"])
def post_tamper_check(
    event_id: str,
    request: Request,
    field: str = Query(default="metric_value",
                       description="manifest field to alter before verifying"),
):
    """Demonstrate the failure path by altering one field before verifying.

    Nothing is written. The stored manifest is untouched; only this response
    reflects the mutation. This exists so the failure can be shown live rather
    than asserted.
    """
    result = verify_event(event_id, tamper_field=field)
    if result is None:
        return _error(request, "not_found", f"No audit event {event_id!r}.", 404)
    return result


app.include_router(api)
