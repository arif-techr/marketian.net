from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Project


class StaticSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return ["core:home", "core:about", "core:services", "core:tools", "core:portfolio", "core:contact"]

    def location(self, item):
        return reverse(item)


class ProjectSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return Project.objects.filter(is_published=True)
