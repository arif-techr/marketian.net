"""
What each destination type needs: its settings, its secret, which of our standard
events it receives by default (and under what name), and which consent it waits for.
The dashboard builds its forms from this; the worker's adapters (../engine) use the
same event names.
"""

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError

STANDARD_EVENTS = [
    "PageView", "ViewContent", "AddToCart", "InitiateCheckout", "AddPaymentInfo",
    "Purchase", "Refund", "Lead", "CompleteRegistration", "Search",
]
CONSENT_KEYS = ["ad_storage", "ad_user_data", "ad_personalization", "analytics_storage"]


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    required: bool = True
    pattern: str = ""  # full-match regular expression for the cleaned value
    help: str = ""
    kind: str = "text"  # text, url, list (comma separated)


@dataclass(frozen=True)
class DestinationType:
    key: str
    label: str
    config_fields: list
    secret_fields: list
    default_event_map: dict
    default_consent: list = field(default_factory=list)


def _map(names):
    return dict(zip(STANDARD_EVENTS, names))


TYPES = {
    "meta": DestinationType(
        key="meta",
        label="Meta (Facebook) Conversions API",
        config_fields=[
            Field("pixel_id", "Pixel ID", pattern=r"\d{10,20}", help="Events Manager → Data sources → your pixel → Settings."),
            Field("test_event_code", "Test event code", required=False, pattern=r"TEST\w{1,20}", help="Only while testing: events then show in Events Manager → Test events."),
            Field("graph_version", "Graph API version", required=False, pattern=r"v\d{2}\.\d", help="Leave empty to use the current default."),
        ],
        secret_fields=[Field("access_token", "Access token", pattern=r"\S{20,512}", help="Events Manager → Settings → Conversions API → Generate access token.")],
        default_event_map=_map(["PageView", "ViewContent", "AddToCart", "InitiateCheckout", "AddPaymentInfo",
                                "Purchase", None, "Lead", "CompleteRegistration", "Search"]),
        default_consent=["ad_storage", "ad_user_data"],
    ),
    "ga4": DestinationType(
        key="ga4",
        label="Google Analytics 4",
        config_fields=[Field("measurement_id", "Measurement ID", pattern=r"G-[A-Z0-9]{4,16}", help="Admin → Data streams → your web stream, like G-AB12CD34EF.")],
        secret_fields=[Field("api_secret", "Measurement Protocol API secret", pattern=r"\S{8,128}", help="Same data stream → Measurement Protocol API secrets → Create.")],
        default_event_map=_map(["page_view", "view_item", "add_to_cart", "begin_checkout", "add_payment_info",
                                "purchase", "refund", "generate_lead", "sign_up", "search"]),
        default_consent=["analytics_storage"],
    ),
    "tiktok": DestinationType(
        key="tiktok",
        label="TikTok Events API",
        config_fields=[
            Field("pixel_code", "Pixel code", pattern=r"[A-Z0-9]{10,30}", help="TikTok Ads Manager → Assets → Events → your web pixel."),
            Field("test_event_code", "Test event code", required=False, pattern=r"TEST\w{1,20}"),
        ],
        secret_fields=[Field("access_token", "Access token", pattern=r"\S{20,512}", help="Pixel settings → Events API → Generate access token.")],
        default_event_map=_map(["Pageview", "ViewContent", "AddToCart", "InitiateCheckout", "AddPaymentInfo",
                                "CompletePayment", None, "SubmitForm", "CompleteRegistration", "Search"]),
        default_consent=["ad_storage", "ad_user_data"],
    ),
    "webhook": DestinationType(
        key="webhook",
        label="Webhook (your own server)",
        config_fields=[
            Field("url", "URL", kind="url", help="We POST each event here as JSON, signed in the X-MT-Signature header."),
            Field("events", "Only these events", required=False, kind="list", help="Comma separated. Leave empty to send every event."),
        ],
        secret_fields=[Field("signing_secret", "Signing secret", pattern=r"\S{16,128}", help="At least 16 characters. Check the HMAC-SHA256 signature with it.")],
        default_event_map={name: name for name in STANDARD_EVENTS},
        default_consent=[],
    ),
}

CHOICES = [(key, kind.label) for key, kind in TYPES.items()]


def get_type(key):
    try:
        return TYPES[key]
    except KeyError:
        raise ValidationError({"type": f"Unknown destination type {key!r}."}) from None


def _clean_value(spec, value):
    if spec.kind == "list":
        items = value if isinstance(value, list) else str(value or "").split(",")
        return [item.strip() for item in items if str(item).strip()]
    value = str(value or "").strip()
    if not value:
        return ""
    if spec.kind == "url":
        parts = urlsplit(value)
        schemes = ("https", "http") if settings.DEBUG else ("https",)
        if parts.scheme not in schemes or not parts.hostname:
            raise ValidationError({spec.name: "Use a full https:// address."})
    elif spec.pattern and not re.fullmatch(spec.pattern, value):
        raise ValidationError({spec.name: f"This doesn't look like a {spec.label.lower()}."})
    return value


def clean_fields(specs, values):
    """Check `values` against the field list. Returns only known fields; drops empty optional ones."""
    values = values or {}
    cleaned, errors = {}, {}
    for spec in specs:
        try:
            value = _clean_value(spec, values.get(spec.name))
        except ValidationError as exc:
            errors.update(exc.message_dict)
            continue
        if value in ("", []):
            if spec.required:
                errors[spec.name] = [f"{spec.label} is required."]
            continue
        cleaned[spec.name] = value
    if errors:
        raise ValidationError(errors)
    return cleaned


def clean_event_map(type_key, event_map):
    """Overrides only: {our event: platform event or None}. Names must be short and plain."""
    cleaned = {}
    for ours, theirs in (event_map or {}).items():
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,59}", str(ours)):
            raise ValidationError({"event_map": f"{ours!r} isn't a valid event name."})
        if theirs is not None and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,59}", str(theirs)):
            raise ValidationError({"event_map": f"{theirs!r} isn't a valid event name for {get_type(type_key).label}."})
        cleaned[ours] = theirs
    return cleaned
