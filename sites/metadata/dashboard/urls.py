from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("app/", views.app, name="app"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
]
