from django.utils import timezone

from .models import SiteProfile


def site_profile(request):
    return {"profile": SiteProfile.load(), "current_year": timezone.now().year}
