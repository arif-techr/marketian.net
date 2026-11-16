from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from workspaces.access import for_workspace

from .models import Site


@login_required
def sites(request):
    sites = for_workspace(Site, request.workspace).prefetch_related("domains")
    return render(request, "tracker/sites.html", {"sites": sites})
