from django.urls import path

from . import views

app_name = "shortener"

# Under /app/: the signed-in part. Short links themselves are routed in product/urls.py.
urlpatterns = [
    path("", views.links, name="links"),
    path("links/<int:pk>/", views.detail, name="detail"),
    path("links/<int:pk>/delete/", views.delete, name="delete"),
    path("links/<int:pk>/qr.<str:kind>", views.qr, name="qr"),
    path("export.csv", views.export, name="export"),
]
