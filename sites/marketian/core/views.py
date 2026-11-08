from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render

from mailer.services import notify_new_contact

from .forms import ContactForm
from .models import Experience, Project, Service, Skill, Testimonial, Tool

CONTACT_LIMIT_PER_HOUR = 5


def home(request):
    projects = Project.objects.filter(is_published=True)
    featured = projects.filter(featured=True)[:3] or projects[:3]
    return render(request, "core/home.html", {
        "services": Service.objects.filter(is_active=True)[:6],
        "projects": featured,
        "testimonials": Testimonial.objects.filter(is_active=True)[:6],
        "tools": Tool.objects.filter(is_active=True)[:3],
    })


def about(request):
    skill_groups = {}
    for skill in Skill.objects.all():
        skill_groups.setdefault(skill.group, []).append(skill)
    return render(request, "core/about.html", {
        "skill_groups": skill_groups,
        "experience": Experience.objects.all(),
    })


def services(request):
    return render(request, "core/services.html", {"services": Service.objects.filter(is_active=True)})


def tools(request):
    return render(request, "core/tools.html", {"tools": Tool.objects.filter(is_active=True)})


def portfolio(request):
    projects = Project.objects.filter(is_published=True)
    categories = sorted(set(projects.values_list("category", flat=True)))
    active = request.GET.get("category", "")
    if active:
        projects = projects.filter(category=active)
    return render(request, "core/portfolio.html", {
        "projects": projects,
        "categories": categories,
        "active_category": active,
    })


def project_detail(request, slug):
    project = get_object_or_404(Project, slug=slug, is_published=True)
    others = Project.objects.filter(is_published=True).exclude(pk=project.pk)[:3]
    return render(request, "core/project_detail.html", {"project": project, "others": others})


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        ip = _client_ip(request)
        rate_key = f"contact-rate:{ip}"
        if cache.get(rate_key, 0) >= CONTACT_LIMIT_PER_HOUR:
            messages.error(request, "You've sent several messages recently. Please try again a bit later.")
        elif form.is_valid():
            if form.is_spam():
                # Pretend success so bots don't learn anything.
                messages.success(request, "Thanks! Your message has been sent.")
                return redirect("core:contact")
            contact_msg = form.save(commit=False)
            contact_msg.ip_address = ip
            contact_msg.save()
            cache.set(rate_key, cache.get(rate_key, 0) + 1, 60 * 60)
            # Failures are logged under Mail → Sent emails; the message itself is already saved.
            notify_new_contact(contact_msg)
            messages.success(request, f"Thanks {contact_msg.name.split()[0]}! Your message has been sent — I'll reply within 24 hours.")
            return redirect("core:contact")
    else:
        form = ContactForm(initial={"subject": request.GET.get("subject", "")})
    return render(request, "core/contact.html", {"form": form})


def robots_txt(request):
    sitemap_url = request.build_absolute_uri("/sitemap.xml")
    return render(request, "robots.txt", {"sitemap_url": sitemap_url}, content_type="text/plain")


def page_not_found(request, exception):
    return render(request, "404.html", status=404)
