"""«Сверка с Гранитом»: monthly reconciliation of our sales with Granit sales documents."""
from datetime import date

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.models import Store
from etl.models import ReconcileSnapshot
from etl.proxy import ProxyApiError
from etl.reconcile import month_documents, month_start, refresh_month, refresh_months, tolerance

MONTHS_SHOWN = 12
SERIOUS_FLAGS = {"leftover"}
MONTH_STATES = {"open", "partial"}


def _parse_month(value: str) -> date:
    try:
        return date.fromisoformat(f"{value}-01")
    except ValueError as exc:
        raise Http404(_("Unknown month.")) from exc


def status_of(diff: float, granit: float, flags: list[dict]) -> str:
    kinds = {f["kind"] for f in flags}
    if kinds & SERIOUS_FLAGS:
        return "bad"
    if abs(diff) <= tolerance():
        return "warn" if kinds - {"diff"} else "ok"
    if granit and abs(diff) <= abs(granit) * 0.001:
        return "warn"
    return "bad"


def _month_row(snap: ReconcileSnapshot) -> dict:
    totals = snap.data.get("totals", {})
    flags = snap.data.get("flags", [])
    state = snap.data.get("state", "closed")
    status = state if state in MONTH_STATES else status_of(totals.get("diff", 0), totals.get("granit_total", 0), flags)
    return {
        "snap": snap,
        "month": snap.month,
        "key": snap.month.strftime("%Y-%m"),
        "totals": totals,
        "flags": flags,
        "state": state,
        "status": status,
    }


def latest_status(day: date | None = None) -> dict | None:
    """Badge for the matrix: the snapshot of the month that contains `day`, else the latest one."""
    snap = None
    if day is not None:
        snap = ReconcileSnapshot.objects.filter(month=month_start(day)).first()
    snap = snap or ReconcileSnapshot.objects.first()
    return _month_row(snap) if snap else None


def _services_pivot(rows: list[dict]) -> dict:
    months = [r["key"] for r in reversed(rows)]
    kinds: dict[int, dict] = {}
    for row in reversed(rows):
        for item in row["snap"].data.get("services", []):
            kind = kinds.setdefault(item["id"], {"name": item["name"], "cells": {}, "new_in": None})
            kind["cells"][row["key"]] = item["granit"]
            if item.get("new") and kind["new_in"] is None:
                kind["new_in"] = row["key"]
    for kind in kinds.values():
        kind["values"] = [kind["cells"].get(m) for m in months]
    return {"months": months, "kinds": sorted(kinds.values(), key=lambda k: k["name"])}


def reconcile_overview(request):
    rows = [_month_row(s) for s in ReconcileSnapshot.objects.all()[:MONTHS_SHOWN]]
    return render(
        request,
        "sales/reconcile.html",
        {
            "rows": rows,
            "current": rows[0] if rows else None,
            "services": _services_pivot(rows),
            "tolerance": tolerance(),
        },
    )


def reconcile_month(request, month: str):
    snap = get_object_or_404(ReconcileSnapshot, month=_parse_month(month))
    row = _month_row(snap)
    tol = tolerance()
    stores = []
    for store in snap.data.get("stores", []):
        flags = [{"kind": k} for k in store.get("flags", [])]
        status = status_of(store["diff"], store["granit_total"], flags)
        if row["state"] in MONTH_STATES and status != "ok":
            status = row["state"]
        stores.append({**store, "status": status})
    return render(
        request,
        "sales/reconcile_month.html",
        {"row": row, "stores": stores, "data": snap.data, "tolerance": tol},
    )


def reconcile_documents(request, month: str, store_id: int):
    snap = get_object_or_404(ReconcileSnapshot, month=_parse_month(month))
    store = get_object_or_404(Store, granit_id=store_id)
    try:
        docs = month_documents(snap.month, store_id)
        error = ""
    except ProxyApiError as exc:
        docs, error = {"rows": [], "total": 0, "checked": 0}, str(exc)
    return render(
        request,
        "sales/reconcile_docs.html",
        {"row": _month_row(snap), "store": store, "docs": docs, "error": error},
    )


@require_POST
def reconcile_refresh(request):
    if not request.user.is_staff:
        raise PermissionDenied
    month = (request.POST.get("month") or "").strip()
    try:
        if month:
            refresh_month(_parse_month(month))
        else:
            refresh_months(date.today(), 2)
    except ProxyApiError as exc:
        messages.error(request, _("Granit is not reachable: %(error)s") % {"error": exc})
    else:
        messages.success(request, _("Reconciliation recalculated."))
    target = request.POST.get("next") or ""
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        target = reverse("sales_reconcile")
    return redirect(target)
