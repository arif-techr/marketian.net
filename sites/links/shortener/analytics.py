"""Visit counting and the numbers behind the stats pages (short links and bio pages)."""
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from . import visitors


def should_count(request):
    """Bots, and the app's own hover prefetch and page swaps, are sent on but not counted."""
    ua = visitors.user_agent(request)
    return not (visitors.is_bot(ua) or request.headers.get("HX-Preloaded") or request.headers.get("HX-Request"))


def visit_fields(request):
    ua = visitors.user_agent(request)
    return {
        "visitor": visitors.visitor_id(request),
        "referrer": visitors.referrer_domain(request),
        "device": visitors.device(ua),
        "browser": visitors.first_match(ua, visitors.BROWSERS),
        "os": visitors.first_match(ua, visitors.SYSTEMS),
    }


def summarize(events):
    """Totals, the last 30 days day by day, and the top sources of a set of visits (clicks or views)."""
    start = timezone.localdate() - timedelta(days=29)
    per_day = dict(events.filter(at__date__gte=start).annotate(day=TruncDate("at")).values_list("day").annotate(n=Count("id")))
    days = [{"day": start + timedelta(days=i), "n": per_day.get(start + timedelta(days=i), 0)} for i in range(30)]
    peak = max(d["n"] for d in days) or 1
    for d in days:
        d["pct"] = round(d["n"] * 100 / peak)

    def top(field, empty):
        rows = list(events.values(field).annotate(n=Count("id")).order_by("-n")[:6])
        total = sum(r["n"] for r in rows) or 1
        return [{"name": r[field] or empty, "n": r["n"], "pct": round(r["n"] * 100 / total)} for r in rows]

    return {
        "unique": events.values("visitor").distinct().count(),
        "last_30": sum(d["n"] for d in days),
        "days": days,
        "tables": [
            ("Where visitors came from", top("referrer", "Direct or unknown")),
            ("Devices", top("device", "Unknown")),
            ("Browsers", top("browser", "Unknown")),
            ("Systems", top("os", "Unknown")),
        ],
    }
