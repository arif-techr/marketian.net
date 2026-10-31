from django.conf import settings


def sign_in_options(request):
    return {"github_enabled": settings.GITHUB_ENABLED}
