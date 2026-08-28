"""HTML adapter: server-rendered board, worklist and drill-down."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from seamly.modules.exception import repository as exception_repo
from seamly.modules.exception.models import STATUS_OPEN

router = APIRouter()
templates = Jinja2Templates(directory="src/seamly/ui/templates")


def _gbp(minor: int) -> str:
    return f"{minor / 100:,.2f}"


templates.env.filters["gbp"] = _gbp


@router.get("/", response_class=HTMLResponse)
async def board(request: Request) -> Any:
    session = request.state.session
    at_risk = await exception_repo.total_at_risk(session)
    recovered = await exception_repo.total_recovered(session)
    rows = await exception_repo.all_exceptions(session)
    open_rows = [r for r in rows if r.status in ("open", "assigned")]
    by_rule: dict[str, int] = {}
    for row in open_rows:
        by_rule[row.rule_id] = by_rule.get(row.rule_id, 0) + row.amount_minor
    return templates.TemplateResponse(
        request,
        "board.html",
        {
            "actor": request.state.actor,
            "role": request.state.role,
            "at_risk_minor": at_risk,
            "recovered_minor": recovered,
            "open_count": len(open_rows),
            "top": open_rows[:8],
            "by_rule": sorted(by_rule.items(), key=lambda kv: kv[1], reverse=True),
        },
    )


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request) -> Any:
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)) -> Any:
    result = await request.state.app_engine.dispatch(
        request.state.session, "auth.login", {"email": email, "password": password}
    )
    if result.is_err:
        err = result.error_or_raise()
        return templates.TemplateResponse(
            request, "login.html", {"error": err.message}, status_code=401
        )
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("seamly_session", result.value["token"], httponly=True, samesite="lax")
    return response


@router.get("/logout")
async def logout(request: Request) -> Any:
    token = request.cookies.get("seamly_session", "")
    await request.state.app_engine.dispatch(request.state.session, "auth.logout", {"token": token})
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("seamly_session")
    return response


@router.get("/worklist", response_class=HTMLResponse)
async def worklist(request: Request) -> Any:
    session = request.state.session
    rows = await exception_repo.all_exceptions(session, STATUS_OPEN)
    return templates.TemplateResponse(
        request,
        "worklist.html",
        {"actor": request.state.actor, "role": request.state.role, "rows": rows},
    )


@router.get("/exceptions/{exception_id}", response_class=HTMLResponse)
async def exception_detail(request: Request, exception_id: int) -> Any:
    session = request.state.session
    record = await exception_repo.get_exception(session, exception_id)
    if record is None:
        return HTMLResponse("Not found", status_code=404)
    recoveries = await exception_repo.recoveries_for(session, record.id)
    return templates.TemplateResponse(
        request,
        "exception.html",
        {
            "actor": request.state.actor,
            "role": request.state.role,
            "record": record,
            "recoveries": recoveries,
        },
    )


@router.post("/exceptions/{exception_id}/assign")
async def assign(request: Request, exception_id: int, owner: str = Form(...)) -> Any:
    result = await request.state.app_engine.dispatch(
        request.state.session, "exception.assign", {"exception_id": exception_id, "owner": owner}
    )
    if result.is_err:
        return HTMLResponse(result.error_or_raise().message, status_code=400)
    return RedirectResponse(f"/exceptions/{exception_id}", status_code=303)


@router.post("/exceptions/{exception_id}/resolve")
async def resolve(
    request: Request,
    exception_id: int,
    amount_minor: int = Form(...),
    evidence: str = Form(...),
) -> Any:
    result = await request.state.app_engine.dispatch(
        request.state.session,
        "exception.resolve",
        {
            "exception_id": exception_id,
            "amount_minor": amount_minor,
            "evidence": evidence,
        },
    )
    if result.is_err:
        return HTMLResponse(result.error_or_raise().message, status_code=400)
    return RedirectResponse(f"/exceptions/{exception_id}", status_code=303)


@router.post("/run-pipeline")
async def run_pipeline(request: Request) -> Any:
    engine = request.state.app_engine
    ingest_result = await engine.dispatch(request.state.session, "ingest.load", {})
    if ingest_result.is_err:
        return HTMLResponse(ingest_result.error_or_raise().message, status_code=400)
    reconcile_result = await engine.dispatch(request.state.session, "reconcile.run", {})
    if reconcile_result.is_err:
        return HTMLResponse(reconcile_result.error_or_raise().message, status_code=400)
    return RedirectResponse("/", status_code=303)
