"""JSON adapter. Thin: no logic beyond calling the engine."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from seamly.modules.exception import repository as exception_repo

router = APIRouter()


class ActionPayload(BaseModel):
    payload: dict[str, Any] = {}


def _engine(request: Request) -> Any:
    return request.state.app_engine


def _session(request: Request) -> Any:
    return request.state.session


async def _dispatch(request: Request, event: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = await _engine(request).dispatch(_session(request), event, payload)
    if result.is_err:
        err = result.error_or_raise()
        raise HTTPException(status_code=400, detail={"code": err.code, "message": err.message})
    return {"ok": True, **(result.value or {})}


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    return {"status": "ok", "actor": request.state.actor, "role": request.state.role}


@router.post("/ingest/run")
async def ingest_run(request: Request, body: ActionPayload | None = None) -> dict[str, Any]:
    return await _dispatch(request, "ingest.load", (body.payload if body else {}))


@router.post("/reconcile/run")
async def reconcile_run(request: Request, body: ActionPayload | None = None) -> dict[str, Any]:
    return await _dispatch(request, "reconcile.run", (body.payload if body else {}))


@router.get("/summary")
async def summary(request: Request) -> dict[str, Any]:
    session = _session(request)
    at_risk = await exception_repo.total_at_risk(session)
    recovered = await exception_repo.total_recovered(session)
    rows = await exception_repo.all_exceptions(session)
    by_rule: dict[str, int] = {}
    for row in rows:
        if row.status in ("open", "assigned"):
            by_rule[row.rule_id] = by_rule.get(row.rule_id, 0) + row.amount_minor
    return {
        "total_at_risk_minor": at_risk,
        "total_recovered_minor": recovered,
        "open_exceptions": sum(1 for r in rows if r.status in ("open", "assigned")),
        "at_risk_by_rule_minor": by_rule,
    }


@router.get("/exceptions")
async def exceptions(request: Request, status: str | None = None) -> list[dict[str, Any]]:
    session = _session(request)
    rows = await exception_repo.all_exceptions(session, status)
    return [
        {
            "id": r.id,
            "rule_id": r.rule_id,
            "amount_minor": r.amount_minor,
            "currency": r.currency,
            "status": r.status,
            "owner": r.owner,
            "formula": r.formula,
            "record_refs": r.record_refs,
            "contract_code": r.contract_code,
        }
        for r in rows
    ]


@router.post("/exceptions/{exception_id}/assign")
async def assign(
    exception_id: int, request: Request, body: ActionPayload | None = None
) -> dict[str, Any]:
    payload = dict(body.payload if body else {})
    payload["exception_id"] = exception_id
    return await _dispatch(request, "exception.assign", payload)


@router.post("/exceptions/{exception_id}/resolve")
async def resolve(
    exception_id: int, request: Request, body: ActionPayload | None = None
) -> dict[str, Any]:
    payload = dict(body.payload if body else {})
    payload["exception_id"] = exception_id
    return await _dispatch(request, "exception.resolve", payload)


@router.post("/exceptions/{exception_id}/accept-risk")
async def accept_risk(
    exception_id: int, request: Request, body: ActionPayload | None = None
) -> dict[str, Any]:
    payload = dict(body.payload if body else {})
    payload["exception_id"] = exception_id
    return await _dispatch(request, "exception.accept_risk", payload)


@router.post("/analyst/ask")
async def analyst_ask(request: Request, body: ActionPayload | None = None) -> dict[str, Any]:
    return await _dispatch(request, "analyst.ask", (body.payload if body else {}))


@router.post("/login")
async def login(request: Request, body: ActionPayload, response: Response) -> dict[str, Any]:
    result = await _engine(request).dispatch(_session(request), "auth.login", body.payload)
    if result.is_err:
        raise HTTPException(
            status_code=401,
            detail={"code": result.error.code, "message": result.error.message},
        )
    token = result.value["token"]
    response.set_cookie("seamly_session", token, httponly=True, samesite="lax")
    return {"ok": True, "name": result.value["name"], "role": result.value["role"]}


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict[str, Any]:
    token = request.cookies.get("seamly_session", "")
    await _engine(request).dispatch(_session(request), "auth.logout", {"token": token})
    response.delete_cookie("seamly_session")
    return {"ok": True}
