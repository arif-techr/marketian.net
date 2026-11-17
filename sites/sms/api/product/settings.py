"""
Settings for the Marketian SMS API (Django + Django REST Framework). It answers the /api/v1
contract (docs/contract.md) that the Next.js panel in ../web and customers' servers use; the
panel is the only thing the public reaches (sms.marketian.net), and it forwards /api/v1 here.

People sign in with their Marketian account over OpenID Connect (accounts.marketian.net).
All values come from environment variables (or `.env`); see `.env.example`.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


PRODUCT_NAME = os.getenv("PRODUCT_NAME", "Marketian SMS")
APP_URL = os.getenv("APP_URL", "https://sms.marketian.net").rstrip("/")
ACCOUNTS_URL = os.getenv("ACCOUNTS_URL", "https://accounts.marketian.net").rstrip("/")

DEBUG = env_bool("DEBUG", True)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-change-me")

# Secrets shared with the panel (../web) or used to protect data. Same names as the Laravel reference.
API_KEY_PEPPER = os.getenv("API_KEY_PEPPER", "dev-insecure-pepper" if DEBUG else "")  # hashes customers' API keys
SETTINGS_ENCRYPTION_KEY = os.getenv("SETTINGS_ENCRYPTION_KEY", "dev-insecure-settings-key" if DEBUG else "")  # secret settings
FRONTEND_PROXY_SECRET = os.getenv("FRONTEND_PROXY_SECRET", "dev-insecure-proxy" if DEBUG else "")  # the panel's forwarded calls
CRON_SECRET = os.getenv("CRON_SECRET", "")  # /api/v1/internal/ready for monitoring

# Refuse to start in production without real secrets (the Docker build's collectstatic is the exception).
if not DEBUG and not env_bool("BUILD_ONLY"):
    for _name in ("SECRET_KEY", "API_KEY_PEPPER", "SETTINGS_ENCRYPTION_KEY", "FRONTEND_PROXY_SECRET"):
        _value = globals()[_name]
        if not _value or _value.startswith("dev-insecure") or _value in ("change-me", "CHANGE_ME_SECRET") or len(_value) < 32:
            raise ImproperlyConfigured(f"{_name} is missing, too short or a placeholder. Set a real one in .env.")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "sms.marketian.net")
ALLOWED_HOSTS += [h for h in ("localhost", "127.0.0.1", "sms-api") if h not in ALLOWED_HOSTS]
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", APP_URL)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.openid_connect",
    "common",
    "accounts",
    "orgs",
    "contacts",
    "messaging",
    "billing",
    "developers",
    "support",
    "system",
]

MIDDLEWARE = [
    "common.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "product.urls"
APPEND_SLASH = False  # API paths are exact, as in the contract

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "product.wsgi.application"

# PostgreSQL when POSTGRES_DB is set (Docker, and the server's shared database), otherwise SQLite
# for quick local tests. Run the full suite on PostgreSQL before merging: money and queue code
# relies on its row locks.
if os.getenv("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB"),
            "USER": os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "postgres"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

REDIS_URL = os.getenv("REDIS_URL", "")
if REDIS_URL:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Dhaka")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- API ------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "common.envelope.exception_handler",
    "UNAUTHENTICATED_USER": None,
}

# --- Sign in with the Marketian account --------------------------------------------
SOCIALACCOUNT_ONLY = True
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_UNIQUE_EMAIL = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_STORE_TOKENS = False
SOCIALACCOUNT_PROVIDERS = {
    "openid_connect": {
        "OAUTH_PKCE_ENABLED": True,
        "APPS": [{
            "provider_id": "marketian",
            "name": "Marketian",
            "client_id": os.getenv("MARKETIAN_CLIENT_ID", ""),
            "secret": os.getenv("MARKETIAN_CLIENT_SECRET", ""),
            "settings": {"server_url": f"{ACCOUNTS_URL}/o"},
        }],
    }
}

# --- Background work (Celery) ----------------------------------------------------
CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_RESULT_BACKEND = None
CELERY_TASK_IGNORE_RESULT = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BEAT_SCHEDULE = {}

# --- Production security ---------------------------------------------------------
if not DEBUG:
    # Only the panel (sms-web) and Caddy reach this service, inside Docker, over plain HTTP.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = env_bool("SECURE_COOKIES", not DEBUG)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
