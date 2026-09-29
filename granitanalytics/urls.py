"""
URL configuration for granitanalytics project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path
from django.views.i18n import set_language

from core.views import health, home

urlpatterns = [
    path("", home, name="home"),
    path("health", health, name="health"),
    path(
        "accounts/login/",
        login_not_required(LoginView.as_view(template_name="registration/login.html")),
        name="login",
    ),
    path(
        "accounts/logout/",
        LogoutView.as_view(),
        name="logout",
    ),
    path("campaigns/", include("campaigns.urls")),
    path("sales/", include("sales.urls")),
    path("promos/", include("promos.urls")),
    path("admin/", admin.site.urls),
    path("i18n/setlang/", login_not_required(set_language), name="set_language"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
