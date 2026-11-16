from django.urls import path

from . import views

app_name = "internal"

urlpatterns = [
    path("caddy-ask", views.caddy_ask, name="caddy_ask"),
    path("healthz", views.healthz, name="healthz"),
]
