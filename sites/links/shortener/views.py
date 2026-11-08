import csv
import io
import segno
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import analytics, visitors
from .forms import CreateLinkForm, EditLinkForm
from .models import RESERVED, Click, Link

PASSWORD_TRIES = 10  # wrong passwords per visitor and link, every 10 minutes


def short_url(request, link):
    return request.build_absolute_uri(f"/{link.slug}")


# ---- Your links (signed in) ----------------------------------------------------

@login_required
def links(request):
    form = CreateLinkForm(request.POST or None, owner=request.user, short_host=request.get_host())
    if request.method == "POST" and form.is_valid():
        link = form.save()
        messages.success(request, "Your short link is ready.")
        return redirect("shortener:detail", pk=link.pk)

    found = request.user.links.all()
    query = request.GET.get("q", "").strip()
    if query:
        found = found.filter(Q(slug__icontains=query) | Q(title__icontains=query) | Q(destination__icontains=query))
    page = Paginator(found, 20).get_page(request.GET.get("page"))
    for link in page:
        link.short = short_url(request, link)
    return render(request, "shortener/links.html", {
        "form": form, "page": page, "query": query,
        "total": request.user.links.count(),
        "open_options": request.method == "POST",
    })


@login_required
def detail(request, pk):
    link = get_object_or_404(Link, pk=pk, owner=request.user)
    form = EditLinkForm(request.POST or None, instance=link, short_host=request.get_host())
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Saved.")
        return redirect("shortener:detail", pk=link.pk)
    return render(request, "shortener/detail.html", {
        "link": link, "short": short_url(request, link), "form": form, **analytics.summarize(link.click_set.all()),
    })


@login_required
@require_POST
def delete(request, pk):
    link = get_object_or_404(Link, pk=pk, owner=request.user)
    link.delete()
    messages.success(request, f"Deleted /{link.slug}. It no longer works.")
    return redirect("shortener:links")


@login_required
def qr(request, pk, kind):
    link = get_object_or_404(Link, pk=pk, owner=request.user)
    code = segno.make(short_url(request, link), error="m")
    out = io.BytesIO()
    if kind == "svg":
        code.save(out, kind="svg", scale=8, border=2, xmldecl=False)
        response = HttpResponse(out.getvalue(), content_type="image/svg+xml")
    else:
        code.save(out, kind="png", scale=12, border=2)
        response = HttpResponse(out.getvalue(), content_type="image/png")
    if request.GET.get("download"):
        response["Content-Disposition"] = f'attachment; filename="{link.slug}-qr.{kind}"'
    return response


@login_required
def export(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="my-links.csv"'
    writer = csv.writer(response)
    writer.writerow(["Short link", "Long link", "Title", "Clicks", "On", "Password", "Stops working", "Created"])
    for link in request.user.links.all():
        writer.writerow([
            short_url(request, link), link.destination, link.title, link.clicks, "yes" if link.is_active else "no",
            "yes" if link.has_password else "no",
            timezone.localtime(link.expires_at).strftime("%Y-%m-%d %H:%M") if link.expires_at else "",
            timezone.localtime(link.created_at).strftime("%Y-%m-%d %H:%M"),
        ])
    return response


# ---- Following a short link (anyone) -----------------------------------------

def find(slug):
    link = Link.objects.filter(slug=slug.lower()).first()
    if link is None:
        raise Http404
    return link


def state_page(request, link):
    """A notice instead of the redirect, or None when the link may be followed."""
    if not link.is_active:
        return render(request, "shortener/state.html", {"title": "This link is turned off",
                      "text": "Its owner switched it off. Ask them for a new one."}, status=410)
    if link.is_expired:
        return render(request, "shortener/state.html", {"title": "This link has expired",
                      "text": "It stopped working on its owner's chosen date."}, status=410)
    return None


def record_click(request, link):
    if analytics.should_count(request):
        Click.objects.create(link=link, **analytics.visit_fields(request))
        Link.objects.filter(pk=link.pk).update(clicks=F("clicks") + 1)


def go(link):
    response = HttpResponseRedirect(link.destination)
    # Every visit must reach us to be counted, and short links stay out of search results.
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex"
    return response


def follow(request, slug):
    if slug.lower() in RESERVED:
        return redirect(f"/{slug.lower()}/")
    try:
        link = find(slug)
    except Http404:
        return render(request, "shortener/state.html", {"title": "This link doesn't exist",
                      "text": "Check that it was typed correctly."}, status=404)
    notice = state_page(request, link)
    if notice:
        return notice

    if link.has_password:
        error = ""
        if request.method == "POST":
            tries_key = f"link-password:{link.pk}:{visitors.visitor_id(request)}"
            tries = cache.get(tries_key, 0)
            if tries >= PASSWORD_TRIES:
                error = "Too many wrong passwords. Try again in 10 minutes."
            elif link.check_password(request.POST.get("password", "")):
                record_click(request, link)
                return go(link)
            else:
                cache.set(tries_key, tries + 1, 600)
                error = "That password is wrong."
        return render(request, "shortener/password.html", {"link": link, "error": error})

    record_click(request, link)
    return go(link)


def preview(request, slug):
    """/name+ : see where a short link goes before visiting it."""
    try:
        link = find(slug)
    except Http404:
        return render(request, "shortener/state.html", {"title": "This link doesn't exist",
                      "text": "Check that it was typed correctly."}, status=404)
    response = render(request, "shortener/preview.html", {
        "link": link, "short": short_url(request, link),
        "notice": state_page(request, link) is not None,
    })
    response["X-Robots-Tag"] = "noindex"
    return response
