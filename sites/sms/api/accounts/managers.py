from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """People sign in with their Marketian account, so users normally have no password here."""

    use_in_migrations = True

    def create_user(self, email, name="", **fields):
        user = self.model(email=self.normalize_email(email).lower(), name=name or email.split("@")[0], **fields)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name="", **fields):
        fields.setdefault("platform_role", "SUPER_ADMIN")
        return self.create_user(email, name, **fields)
