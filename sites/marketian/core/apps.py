from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from allauth.account.signals import user_logged_in

        from .admin_signin import sync_staff

        user_logged_in.connect(sync_staff, dispatch_uid="core-sync-staff")
