"""Fill an empty site with starter content you can then edit in the admin.

    python manage.py seed_demo            # only adds content where none exists
    python manage.py seed_demo --reset    # wipes services/projects/skills/etc. first
"""

import datetime

from django.core.management.base import BaseCommand

from core.models import Experience, Project, Service, SiteProfile, Skill, Testimonial, Tool

SERVICES = [
    ("SEO & Content Strategy", "search", "Rank higher on Google and turn organic visitors into customers.",
     "Technical audits, keyword research and content that answers what your buyers actually search for.",
     "Technical SEO audit\nKeyword & competitor research\nOn-page optimization\nContent plans & blog writing\nLocal SEO & Google Business Profile"),
    ("Paid Advertising", "megaphone", "Profitable Facebook, Instagram and Google Ads campaigns.",
     "Full-funnel campaigns built around your margins — not vanity metrics.",
     "Meta (Facebook & Instagram) Ads\nGoogle Search & Performance Max\nAudience & pixel setup\nA/B creative testing\nWeekly ROAS reporting"),
    ("Social Media Marketing", "share", "Grow an engaged community that trusts your brand.",
     "Content calendars, design and community management that keep your brand top of mind.",
     "Content calendar & strategy\nPost & reel design\nCommunity management\nInfluencer outreach"),
    ("Website Development", "code", "Fast, beautiful websites built to convert visitors.",
     "Custom websites and landing pages built with Django, WordPress or Shopify — mobile-first and SEO-ready.",
     "Custom Django & WordPress sites\nLanding pages that convert\nE-commerce (Shopify / WooCommerce)\nSpeed & Core Web Vitals optimization"),
    ("Analytics & Tracking", "chart", "Know exactly which marketing dollars are working.",
     "Clean tracking and dashboards so every decision is backed by data.",
     "GA4 & Google Tag Manager\nConversion tracking & server-side tagging\nLooker Studio dashboards\nMonthly insight reports"),
    ("Email Marketing", "mail", "Automated email flows that sell while you sleep.",
     "Welcome series, abandoned cart and newsletters that nurture leads into loyal customers.",
     "Klaviyo & Mailchimp setup\nAutomated flows\nNewsletter design\nList growth strategy"),
]

PROJECTS = [
    ("E-commerce SEO Overhaul", "SEO", "Fashion Retail Brand", "#6d5efc", True,
     "Took a fashion store from page 4 to the top 3 for its core product keywords in six months.",
     "The store had hundreds of products but almost no organic traffic. Thin product pages, duplicate content and a slow site were holding it back.",
     "I ran a full technical audit, fixed crawl and indexation issues, rewrote category and product copy around buyer-intent keywords and launched a monthly content plan with internal linking.",
     "+240% organic traffic\n+180% organic revenue\n38 keywords in top 3",
     "SEO, Content, Technical audit, Shopify", datetime.date(2026, 3, 1)),
    ("Meta Ads Lead Generation", "Paid Ads", "Real Estate Agency", "#0ea5e9", True,
     "Cut cost-per-lead by 62% with a full-funnel Facebook & Instagram campaign.",
     "The agency was spending heavily on boosted posts with very few qualified leads.",
     "I rebuilt the account structure, created video and carousel creatives, set up lead forms with qualifying questions and retargeting audiences.",
     "-62% cost per lead\n4.1x return on ad spend\n900+ qualified leads",
     "Meta Ads, Lead Gen, Creative, Retargeting", datetime.date(2025, 11, 1)),
    ("Restaurant Website & Booking", "Web Development", "Local Restaurant Group", "#f472b6", True,
     "A fast, mobile-first website with online table booking and menu management.",
     "Customers couldn't find the menu or book online, and the old site was slow on mobile.",
     "I designed and built a Django website with an editable menu, online reservations and local SEO for every branch.",
     "+3x online bookings\n1.2s mobile load time\nTop 3 in Google Maps",
     "Django, UI Design, Local SEO", datetime.date(2025, 8, 1)),
    ("Brand Social Growth", "Social Media", "Skincare Startup", "#22c55e", False,
     "Grew an Instagram community from 2k to 45k followers with consistent, on-brand content.",
     "A new skincare brand with great products but no recognizable presence online.",
     "A content pillar strategy, reels-first production schedule and micro-influencer partnerships.",
     "2k → 45k followers\n8.4% engagement rate\n+65% website sessions from social",
     "Instagram, Reels, Influencers", datetime.date(2025, 5, 1)),
    ("Analytics Dashboard Setup", "Analytics", "SaaS Company", "#f59e0b", False,
     "GA4, GTM and a live Looker Studio dashboard that unified data from five channels.",
     "Marketing data was spread across five tools and nobody trusted the numbers.",
     "Implemented GA4 with GTM, server-side conversion tracking and a single dashboard for leadership.",
     "5 channels unified\n100% conversion tracking accuracy\nHours of reporting saved weekly",
     "GA4, GTM, Looker Studio", datetime.date(2025, 2, 1)),
    ("Email Automation Flows", "Email Marketing", "Online Bookstore", "#8b5cf6", False,
     "Automated Klaviyo flows that now generate 30% of total store revenue.",
     "The store only sent occasional newsletters and had no automation.",
     "Built welcome, browse-abandonment, cart-abandonment and win-back flows with segmented campaigns.",
     "30% of revenue from email\n52% open rate\n+22% repeat purchases",
     "Klaviyo, Automation, Copywriting", datetime.date(2024, 10, 1)),
]

SKILLS = [
    ("Marketing", [("SEO", 95), ("Meta Ads", 92), ("Google Ads", 88), ("Content Strategy", 90), ("Email Marketing", 85)]),
    ("Technical", [("Django / Python", 85), ("HTML / CSS / JS", 88), ("WordPress", 90), ("GA4 & Tag Manager", 92), ("Looker Studio", 84)]),
]

EXPERIENCE = [
    ("Founder & Lead Marketer", "Marketian", "2022 — Present",
     "Helping brands grow with SEO, paid ads and conversion-focused websites."),
    ("Digital Marketing Specialist", "Agency / Freelance", "2020 — 2022",
     "Managed campaigns and SEO for e-commerce, real estate and local businesses."),
    ("Web Developer", "Freelance", "2018 — 2020",
     "Built websites and landing pages for small businesses and startups."),
]

TESTIMONIALS = [
    ("Sarah Ahmed", "Founder, Fashion Retail Brand",
     "Our organic sales nearly tripled. Clear communication, honest reporting and real results — highly recommended."),
    ("Rahim Chowdhury", "Director, Real Estate Agency",
     "We finally get leads that actually convert. The campaigns paid for themselves in the first month."),
    ("Emily Carter", "Marketing Lead, SaaS Company",
     "For the first time our whole team trusts the numbers. The dashboard is now part of every meeting."),
]


TOOLS = [
    (
        "WA Broadcaster", "whatsapp", Tool.INVITE, "https://wa.marketian.net",
        "Send one WhatsApp message to many customers, safely paced and tracked.",
        "Link your WhatsApp numbers by QR code, pick your contacts and send personalised messages "
        "that go out one by one with natural pauses, while you watch every delivery live.",
        "Link several WhatsApp numbers and share the sending between them\n"
        "Import contacts from Excel or CSV and organise them into lists\n"
        "Personal messages with {name} and your own columns\n"
        "Schedule broadcasts and follow them live\n"
        "Reports by day, campaign and number\n"
        "Team members with their own sign-in",
    ),
    (
        "Metadata", "search", Tool.SOON, "https://metadata.marketian.net",
        "Placeholder: describe Metadata in the admin panel.",
        "",
        "",
    ),
]


class Command(BaseCommand):
    help = "Populate the site with editable starter content."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing content first.")

    def handle(self, *args, reset=False, **options):
        if reset:
            for model in (Service, Tool, Project, Skill, Experience, Testimonial):
                model.objects.all().delete()

        profile = SiteProfile.load()
        if not profile.short_bio:
            profile.name = "Ariful Islam"
            profile.role = "Digital Marketer & Web Developer"
            profile.tagline = "I help brands grow with data-driven marketing and websites that convert."
            profile.short_bio = (
                "I'm a digital marketer and web developer who blends creative strategy with clean code "
                "to help businesses get found, win customers and grow."
            )
            profile.about = (
                "I started out building websites for local businesses and quickly realized a beautiful site is only "
                "half the story — people need to find it, trust it and act on it.\n\n"
                "That's why I founded Marketian: a one-stop partner for SEO, paid advertising, social media and "
                "web development. I've worked with fashion brands, real estate agencies, restaurants and SaaS "
                "companies, always focused on numbers that matter — leads, sales and return on investment.\n\n"
                "When I'm not optimizing campaigns, I'm learning new tools, writing about marketing and helping "
                "small businesses compete with the big players."
            )
            profile.location = "Rajshahi, Bangladesh"
            profile.email = "hello@marketian.net"
            profile.linkedin = "https://www.linkedin.com/"
            profile.facebook = "https://www.facebook.com/"
            profile.github = "https://github.com/"
            profile.save()

        if not Service.objects.exists():
            for i, (title, icon, summary, desc, features) in enumerate(SERVICES):
                Service.objects.create(title=title, icon=icon, summary=summary, description=desc, features=features, order=i)

        if not Tool.objects.exists():
            for i, (name, icon, status, url, tagline, desc, features) in enumerate(TOOLS):
                Tool.objects.create(name=name, icon=icon, status=status, url=url, tagline=tagline,
                                    description=desc, features=features, order=i)

        if not Project.objects.exists():
            for i, (title, cat, client, accent, featured, summary, challenge, solution, results, tags, done) in enumerate(PROJECTS):
                Project.objects.create(
                    title=title, category=cat, client=client, accent=accent, featured=featured, summary=summary,
                    challenge=challenge, solution=solution, results=results, tags=tags, completed=done, order=i,
                )

        if not Skill.objects.exists():
            for group, skills in SKILLS:
                for i, (name, level) in enumerate(skills):
                    Skill.objects.create(name=name, level=level, group=group, order=i)

        if not Experience.objects.exists():
            for i, (title, org, period, desc) in enumerate(EXPERIENCE):
                Experience.objects.create(title=title, organization=org, period=period, description=desc, order=i)

        if not Testimonial.objects.exists():
            for i, (name, position, quote) in enumerate(TESTIMONIALS):
                Testimonial.objects.create(name=name, position=position, quote=quote, order=i)

        self.stdout.write(self.style.SUCCESS("Starter content ready. Edit everything at /admin/."))
