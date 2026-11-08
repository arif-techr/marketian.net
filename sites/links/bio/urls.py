from django.urls import path

from . import views

app_name = "bio"

# Under /app/page/: editing your bio page. The page itself is /@handle (product/urls.py).
urlpatterns = [
    path("", views.items, name="items"),
    path("new/", views.create, name="create"),
    path("items/<int:pk>/", views.item_edit, name="item_edit"),
    path("items/<int:pk>/<str:action>/", views.item_action, name="item_action"),
    path("appearance/", views.appearance, name="appearance"),
    path("socials/", views.socials, name="socials"),
    path("settings/", views.settings_view, name="settings"),
    path("stats/", views.stats, name="stats"),
    path("subscribers/", views.subscribers, name="subscribers"),
    path("subscribers/<int:pk>/delete/", views.subscriber_delete, name="subscriber_delete"),
    path("qr.<str:kind>", views.qr, name="qr"),
]
