from django.urls import path

from . import views

urlpatterns = [
    path("sharing/", views.overview),
    path("sharing/invites/", views.create_invite),
    path("sharing/invites/<int:pk>/new-code/", views.new_code),
    path("sharing/invites/<int:pk>/cancel/", views.cancel_invite),
    path("sharing/invites/<int:pk>/accept/", views.accept_invite),
    path("sharing/invites/<int:pk>/decline/", views.decline_invite),
    path("sharing/shares/<int:pk>/", views.remove_share),
]
