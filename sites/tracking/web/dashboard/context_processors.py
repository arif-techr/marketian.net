from django.conf import settings


def product(request):
    return {
        "product_name": settings.PRODUCT_NAME,
        "product_tagline": settings.PRODUCT_TAGLINE,
        "accounts_url": settings.ACCOUNTS_URL,
    }
