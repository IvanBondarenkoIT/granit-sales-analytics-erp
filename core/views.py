from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_not_required
from django.db import connection
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from core.forms import RegisterForm


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


@login_not_required
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


@login_not_required
@require_http_methods(["GET", "POST"])
def register(request):
    if not settings.ALLOW_REGISTRATION:
        return HttpResponseForbidden(_("Registration is closed."))
    if request.user.is_authenticated:
        return redirect("home")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, _("Account created. Welcome!"))
        return redirect("home")
    return render(request, "registration/register.html", {"form": form})
