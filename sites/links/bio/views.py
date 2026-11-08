import csv
import io
from functools import wraps

import segno
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count, F, Q
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from shortener import analytics, visitors

from .forms import AppearanceForm, CreatePageForm, ItemForm, ProfileForm, SettingsForm, SocialsForm, SubscribeForm
from .models import THEMES, Event, Item, Page

SIGNUPS_PER_HOUR = 5  # email sign-ups per visitor and page


def page_url(request, page):
    return request.build_absolute_uri(f"/@{page.handle}")


def with_page(view):
    """Signed-in owner views: request.page is their bio page (made first if they have none)."""
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        request.page = Page.objects.filter(owner=request.user).first()
        if request.page is None:
            return redirect("bio:create")
        return view(request, *args, **kwargs)
    return wrapper


def editor(request, tab, context):
    return render(request, f"bio/{tab}.html", {
        "page": request.page, "tab": tab, "public_url": page_url(request, request.page), **context,
    })


# ---- Making and editing your page ------------------------------------------------

@login_required
def create(request):
    if Page.objects.filter(owner=request.user).exists():
        return redirect("bio:items")
    suggested = request.user.email.split("@")[0].lower() if request.user.email else ""
    form = CreatePageForm(request.POST or None, initial={"title": request.user.get_full_name(), "handle": suggested})
    if request.method == "POST" and form.is_valid():
        page = form.save(commit=False)
        page.owner = request.user
        page.save()
        messages.success(request, "Your page is ready. Add your first links.")
        return redirect("bio:items")
    return render(request, "bio/create.html", {"form": form})


@with_page
def items(request):
    form = ItemForm(request.POST or None, initial={"is_active": True})
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.page = request.page
        # New items go to the top, like Linktree.
        request.page.items.update(position=F("position") + 1)
        item.position = 0
        item.save()
        messages.success(request, f"Added “{item.title}”.")
        return redirect("bio:items")
    return editor(request, "items", {"form": form, "items": request.page.items.all()})


@with_page
def item_edit(request, pk):
    item = get_object_or_404(Item, pk=pk, page=request.page)
    form = ItemForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Saved.")
        return redirect("bio:items")
    return editor(request, "item_edit", {"form": form, "item": item})


@with_page
@require_POST
def item_action(request, pk, action):
    item = get_object_or_404(Item, pk=pk, page=request.page)
    if action == "delete":
        item.delete()
        messages.success(request, f"Deleted “{item.title}”.")
    elif action == "toggle":
        item.is_active = not item.is_active
        item.save(update_fields=["is_active"])
    elif action in ("up", "down"):
        ordered = list(request.page.items.all())
        i = ordered.index(item)
        j = i - 1 if action == "up" else i + 1
        if 0 <= j < len(ordered):
            ordered[i], ordered[j] = ordered[j], ordered[i]
            for position, each in enumerate(ordered):
                if each.position != position:
                    each.position = position
                    each.save(update_fields=["position"])
    else:
        raise Http404
    return redirect("bio:items")


@with_page
def appearance(request):
    page = request.page
    profile = ProfileForm(request.POST or None, request.FILES or None, instance=page, prefix="profile")
    look = AppearanceForm(request.POST or None, instance=page, prefix="look")
    if request.method == "POST" and profile.is_valid() and look.is_valid():
        profile.save()
        look.save()
        messages.success(request, "Saved.")
        return redirect("bio:appearance")
    return editor(request, "appearance", {"profile": profile, "look": look, "themes": THEMES})


@with_page
def socials(request):
    form = SocialsForm(request.POST or None, instance=request.page)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Saved.")
        return redirect("bio:socials")
    return editor(request, "socials", {"form": form})


@with_page
def settings_view(request):
    form = SettingsForm(request.POST or None, instance=request.page)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Saved.")
        return redirect("bio:settings")
    return editor(request, "settings", {"form": form})


@with_page
def stats(request):
    page = request.page
    views = page.events.filter(kind=Event.VIEW)
    clicks = page.events.filter(kind=Event.CLICK)
    total_views, total_clicks = views.count(), clicks.count()
    return editor(request, "stats", {
        **analytics.summarize(views),
        "total_views": total_views,
        "total_clicks": total_clicks,
        "ctr": round(total_clicks * 100 / total_views) if total_views else 0,
        "item_clicks": page.items.exclude(kind=Item.HEADER).annotate(
            unique=Count("events__visitor", filter=Q(events__kind=Event.CLICK), distinct=True)
        ).order_by("-clicks"),
    })


@with_page
def subscribers(request):
    if request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{request.page.handle}-subscribers.csv"'
        writer = csv.writer(response)
        writer.writerow(["Email", "Signed up"])
        for sub in request.page.subscribers.all():
            writer.writerow([sub.email, sub.created_at.strftime("%Y-%m-%d %H:%M")])
        return response
    return editor(request, "subscribers", {"subscribers": request.page.subscribers.all()})


@with_page
@require_POST
def subscriber_delete(request, pk):
    request.page.subscribers.filter(pk=pk).delete()
    return redirect("bio:subscribers")


@with_page
def qr(request, kind):
    code = segno.make(page_url(request, request.page), error="m")
    out = io.BytesIO()
    if kind == "svg":
        code.save(out, kind="svg", scale=8, border=2, xmldecl=False)
        response = HttpResponse(out.getvalue(), content_type="image/svg+xml")
    else:
        code.save(out, kind="png", scale=12, border=2)
        response = HttpResponse(out.getvalue(), content_type="image/png")
    if request.GET.get("download"):
        response["Content-Disposition"] = f'attachment; filename="{request.page.handle}-qr.{kind}"'
    return response


# ---- The public page: links.marketian.net/@handle --------------------------------

def find(handle):
    return get_object_or_404(Page.objects.select_related("owner"), handle=handle.lower())


def record(request, page, kind, item=None):
    if not analytics.should_count(request) or request.user == page.owner:
        return False
    Event.objects.create(page=page, item=item, kind=kind, **analytics.visit_fields(request))
    return True


@xframe_options_sameorigin  # the editor shows it in a phone-sized preview
def public(request, handle):
    page = find(handle)
    preview = request.GET.get("preview") == "1" and request.user == page.owner
    if not page.is_published and not preview:
        return render(request, "bio/unavailable.html", status=404)
    if not preview and record(request, page, Event.VIEW):
        Page.objects.filter(pk=page.pk).update(views=F("views") + 1)
    return render(request, "bio/public.html", {
        "page": page, "items": page.visible_items(), "colors": page.colors, "preview": preview,
        "show_warning": page.sensitive and request.GET.get("continue") != "1" and not preview,
        "subscribed": request.GET.get("subscribed") == "1",
        "subscribe_form": SubscribeForm(),
        "page_url": page_url(request, page),
    })


def follow(request, handle, pk):
    page = find(handle)
    item = get_object_or_404(Item, pk=pk, page=page)
    if not page.is_published or item.kind == Item.HEADER or not item.is_visible():
        return redirect(f"/@{page.handle}")
    if record(request, page, Event.CLICK, item):
        Item.objects.filter(pk=item.pk).update(clicks=F("clicks") + 1)
    response = HttpResponseRedirect(item.url)
    response["Cache-Control"] = "private, no-store"
    return response


@require_POST
def subscribe(request, handle):
    page = find(handle)
    if not (page.is_published and page.collect_emails):
        raise Http404
    form = SubscribeForm(request.POST)
    limit_key = f"bio-signup:{page.pk}:{visitors.visitor_id(request)}"
    if form.is_valid() and not form.is_spam() and cache.get(limit_key, 0) < SIGNUPS_PER_HOUR:
        cache.set(limit_key, cache.get(limit_key, 0) + 1, 3600)
        # Already signed up: same thank-you, nothing new to store.
        page.subscribers.get_or_create(email=form.cleaned_data["email"].lower())
    # Always the same answer, so the form can't be used to find out who signed up.
    return redirect(f"/@{page.handle}?subscribed=1#signup")

