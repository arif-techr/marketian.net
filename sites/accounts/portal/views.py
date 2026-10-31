from urllib.parse import urlsplit

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from oauth2_provider.models import get_application_model


def product_links():
    """Every registered product, with the address of its home page."""
    products = []
    for app in get_application_model().objects.order_by("name"):
        first_uri = (app.redirect_uris or "").split()
        if first_uri:
            parts = urlsplit(first_uri[0])
            products.append({"name": app.name, "url": f"{parts.scheme}://{parts.netloc}/"})
    return products


@login_required
def home(request):
    return render(request, "portal/home.html", {
        "github": SocialAccount.objects.filter(user=request.user, provider="github").first(),
        "products": product_links(),
    })
