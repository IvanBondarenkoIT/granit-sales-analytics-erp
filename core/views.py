from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _


def home(request):
    """Home page - project overview and navigation."""
    context = {
        "project_name": _("Granit Sales Analytics ERP"),
        "apps": [
            {
                "name": _("SMS Campaign Analysis"),
                "description": _("Upload Excel, analyze customer purchase lift"),
                "status": _("Stage 3 — Ready"),
                "url": "campaign_list",
            },
            {
                "name": _("Sales Explorer"),
                "description": _("Filter and explore sales by product, client, store, period"),
                "status": _("Stage 4 — Ready"),
                "url": "sales_explorer",
            },
            {
                "name": _("Promotion Effectiveness"),
                "description": _("Compare promo results vs baseline and YoY"),
                "status": _("Stage 5 — Ready"),
                "url": "promo_list",
            },
        ],
    }
    return render(request, "core/home.html", context)


def health(request):
    """Liveness/readiness for Docker and the deploy hub. No auth."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # noqa: BLE001 — health must not leak DB details
        return JsonResponse(
            {"status": "error", "app": "granit-analytics"},
            status=503,
        )
    return JsonResponse({"status": "ok", "app": "granit-analytics"})
