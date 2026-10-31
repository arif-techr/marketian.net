from django.core.management.base import BaseCommand, CommandError
from oauth2_provider.generators import generate_client_secret
from oauth2_provider.models import get_application_model

Application = get_application_model()


class Command(BaseCommand):
    help = (
        "Register a product so it can use 'Sign in with your Marketian account'. "
        "Prints the client ID and secret to put in the product's .env."
    )

    def add_arguments(self, parser):
        parser.add_argument("name", help="Short product name, e.g. metadata")
        parser.add_argument("url", help="The product's address, e.g. https://metadata.marketian.net")
        parser.add_argument("--reset-secret", action="store_true", help="Issue a new secret for an existing product")

    def handle(self, name, url, reset_secret, **options):
        url = url.rstrip("/")
        if not url.startswith(("https://", "http://")):
            raise CommandError("The URL must start with https://")

        app = Application.objects.filter(name=name).first()
        if app and not reset_secret:
            raise CommandError(f'"{name}" is already registered. Use --reset-secret to issue a new secret.')

        secret = generate_client_secret()
        if app is None:
            app = Application(name=name)
        app.client_type = Application.CLIENT_CONFIDENTIAL
        app.authorization_grant_type = Application.GRANT_AUTHORIZATION_CODE
        app.algorithm = Application.RS256_ALGORITHM
        app.redirect_uris = f"{url}/accounts/oidc/marketian/login/callback/"
        app.post_logout_redirect_uris = f"{url}/"
        app.skip_authorization = True  # our own products: no "allow access?" screen
        app.client_secret = secret  # stored hashed; shown only now
        app.save()

        self.stdout.write(self.style.SUCCESS(f'"{name}" can now sign people in. Put these lines in its .env:\n'))
        self.stdout.write(f"MARKETIAN_CLIENT_ID={app.client_id}")
        self.stdout.write(f"MARKETIAN_CLIENT_SECRET={secret}")
