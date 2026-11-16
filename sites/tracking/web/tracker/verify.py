"""
Checks that a client's domain really points at us before Caddy may get it a certificate.

Subdomain mode: data.shop.com must be a CNAME to EDGE_CNAME_TARGET, or have an A
record with EDGE_PUBLIC_IP. Same-origin mode: https://shop.com/<prefix>/_v (their
server forwards it to us) must answer with the domain's verify_token.
DOMAIN_VERIFY_MODE=trust skips the check (local only).
"""

import urllib.request
from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone

from .models import Domain

FAILS_BEFORE_FAILING = 3


@dataclass
class Result:
    ok: bool
    message: str
    seen: dict


def _lookup(resolver, hostname, record):
    import dns.exception
    import dns.resolver

    try:
        return [str(r.target if record == "CNAME" else r).rstrip(".").lower() for r in resolver.resolve(hostname, record)]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
        return []


def check_dns(hostname, resolver=None):
    if resolver is None:
        import dns.resolver

        resolver = dns.resolver.Resolver()
        resolver.lifetime = 5
    target, ip = settings.EDGE_CNAME_TARGET, settings.EDGE_PUBLIC_IP
    cnames = _lookup(resolver, hostname, "CNAME")
    seen = {"cname": cnames[0] if cnames else "", "a": []}
    if target in cnames:
        return Result(True, f"{hostname} points to {target}.", seen)
    seen["a"] = _lookup(resolver, hostname, "A")
    if ip and ip in seen["a"]:
        return Result(True, f"{hostname} points to {ip}.", seen)
    if cnames:
        return Result(False, f"{hostname} points to {cnames[0]}, not {target}. Change the CNAME record.", seen)
    if seen["a"]:
        # Usually Cloudflare's proxy (orange cloud) hiding the CNAME behind its own addresses.
        return Result(False, f"{hostname} has an A record for {', '.join(seen['a'])}, not a CNAME to {target}. "
                             "On Cloudflare, set the record to 'DNS only' (grey cloud).", seen)
    return Result(False, f"No DNS record for {hostname} yet. Add a CNAME to {target}; new records can take a few minutes.", seen)


def check_same_origin(domain, fetch=None):
    url = f"https://{domain.hostname}/{domain.site.path_prefix}/_v"
    fetch = fetch or _fetch
    try:
        body = fetch(url)
    except Exception as exc:
        return Result(False, f"Couldn't open {url} ({exc.__class__.__name__}). Check the forwarding rule on the shop's server.", {"url": url})
    if body.strip() == domain.verify_token:
        return Result(True, f"{url} answers with the right token.", {"url": url})
    return Result(False, f"{url} answered, but not with this domain's token. Check that it forwards to {settings.EDGE_CNAME_TARGET}.", {"url": url})


def _fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "MarketianTracking-Verify/1"})
    with urllib.request.urlopen(request, timeout=8) as response:
        return response.read(200).decode("utf-8", "replace")


def verify_domain(domain, resolver=None, fetch=None):
    """Check now and save the outcome. A verified domain that fails 3 checks in a row becomes failing
    (it keeps serving: a DNS hiccup shouldn't stop a shop's tracking)."""
    if domain.status == Domain.DISABLED:
        return Result(False, "This domain is turned off.", domain.dns_seen)
    if settings.DOMAIN_VERIFY_MODE == "trust":
        result = Result(True, "Trusted without a DNS check (DOMAIN_VERIFY_MODE=trust).", {})
    elif domain.mode == Domain.SAME_ORIGIN:
        result = check_same_origin(domain, fetch)
    else:
        result = check_dns(domain.hostname, resolver)

    now = timezone.now()
    domain.dns_seen = result.seen
    domain.last_checked_at = now
    if result.ok:
        domain.fail_count = 0
        if domain.status != Domain.VERIFIED:
            domain.status, domain.verified_at = Domain.VERIFIED, now
    elif domain.status in (Domain.VERIFIED, Domain.FAILING):
        domain.fail_count += 1
        if domain.fail_count >= FAILS_BEFORE_FAILING:
            domain.status = Domain.FAILING
    domain.save()
    return result
