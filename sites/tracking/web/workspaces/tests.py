from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from tracker.models import Domain, Site

from .access import audit, for_workspace, get_for_workspace_or_404, role_required
from .models import AuditLog, Workspace, WorkspaceMember

User = get_user_model()


class FirstSignInTests(TestCase):
    def test_first_sign_in_creates_a_workspace_they_own(self):
        user = User.objects.create_user("jane", "jane@example.com")
        self.client.force_login(user)
        response = self.client.get(reverse("tracker:sites"))
        membership = WorkspaceMember.objects.get(user=user)
        self.assertEqual(membership.role, WorkspaceMember.OWNER)
        self.assertEqual(response.wsgi_request.workspace, membership.workspace)
        self.assertEqual(membership.workspace.slug, "jane")

        self.client.get(reverse("tracker:sites"))
        self.assertEqual(Workspace.objects.count(), 1)  # not a second one on the next visit

    def test_slugs_stay_unique(self):
        Workspace.objects.create(name="Taken", slug="jane")
        workspace = Workspace.personal_for(User.objects.create_user("jane2", "jane@example.org"))
        self.assertTrue(workspace.slug.startswith("jane-"))

    def test_a_member_of_another_workspace_lands_there(self):
        owner = User.objects.create_user("owner", "owner@example.com")
        team = Workspace.personal_for(owner)
        viewer = User.objects.create_user("viewer", "viewer@example.com")
        WorkspaceMember.objects.create(workspace=team, user=viewer, role=WorkspaceMember.VIEWER)
        self.client.force_login(viewer)
        response = self.client.get(reverse("tracker:sites"))
        self.assertEqual(response.wsgi_request.workspace, team)
        self.assertEqual(Workspace.objects.count(), 1)


class TenancyTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", "alice@example.com")
        self.bob = User.objects.create_user("bob", "bob@example.com")
        self.alice_ws = Workspace.personal_for(self.alice)
        self.bob_ws = Workspace.personal_for(self.bob)
        self.bob_site = Site.objects.create(workspace=self.bob_ws, name="Bob shop", primary_domain="bob.com")
        self.bob_domain = Domain.objects.create(site=self.bob_site, hostname="data.bob.com")

    def request_for(self, user, workspace):
        request = RequestFactory().get("/")
        request.user, request.workspace = user, workspace
        request.membership = WorkspaceMember.objects.get(user=user, workspace=workspace)
        return request

    def test_another_workspaces_objects_are_not_found(self):
        request = self.request_for(self.alice, self.alice_ws)
        with self.assertRaises(Http404):
            get_for_workspace_or_404(Site, request, pk=self.bob_site.pk)
        with self.assertRaises(Http404):
            get_for_workspace_or_404(Domain, request, pk=self.bob_domain.pk)
        self.assertFalse(for_workspace(Site, self.alice_ws).exists())

    def test_own_objects_are_found(self):
        request = self.request_for(self.bob, self.bob_ws)
        self.assertEqual(get_for_workspace_or_404(Domain, request, pk=self.bob_domain.pk), self.bob_domain)

    def test_other_people_never_see_the_site_list(self):
        self.client.force_login(self.alice)
        self.assertNotContains(self.client.get(reverse("tracker:sites")), "Bob shop")
        self.client.force_login(self.bob)
        self.assertContains(self.client.get(reverse("tracker:sites")), "Bob shop")


class RoleTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", "owner@example.com")
        self.workspace = Workspace.personal_for(self.owner)

    def call(self, user, role, needed):
        WorkspaceMember.objects.update_or_create(workspace=self.workspace, user=user, defaults={"role": role})
        request = RequestFactory().post("/")
        request.user, request.workspace = user, self.workspace
        request.membership = WorkspaceMember.objects.get(user=user, workspace=self.workspace)
        return role_required(needed)(lambda r: HttpResponse("ok"))(request)

    def test_roles_are_ranked(self):
        user = User.objects.create_user("x", "x@example.com")
        self.assertEqual(self.call(user, "admin", "member").status_code, 200)
        self.assertEqual(self.call(user, "admin", "admin").status_code, 200)
        with self.assertRaises(PermissionDenied):
            self.call(user, "viewer", "member")
        with self.assertRaises(PermissionDenied):
            self.call(user, "admin", "owner")

    def test_unknown_role_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            role_required("boss")

    def test_audit_records_who_and_what(self):
        site = Site.objects.create(workspace=self.workspace, name="Shop", primary_domain="shop.com")
        request = RequestFactory().post("/", HTTP_X_FORWARDED_FOR="203.0.113.9, 10.0.0.2")
        request.user, request.workspace = self.owner, self.workspace
        entry = audit(request, "site.create", site, name="Shop")
        self.assertEqual((entry.actor, entry.target_type, entry.target_id, entry.ip), (self.owner, "site", str(site.pk), "203.0.113.9"))
        self.assertEqual(AuditLog.objects.get().details, {"name": "Shop"})

    def test_audit_ignores_a_bad_ip_header(self):
        request = RequestFactory().post("/", HTTP_X_FORWARDED_FOR="unknown", REMOTE_ADDR="")
        request.user, request.workspace = self.owner, self.workspace
        self.assertIsNone(audit(request, "workspace.rename").ip)
