from django.conf import settings


def auth_flags(request):
    return {
        "ALLOW_REGISTRATION": settings.ALLOW_REGISTRATION,
    }
