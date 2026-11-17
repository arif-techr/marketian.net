import json
import os
import subprocess
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase

from accounts.models import User
from billing.models import Wallet
from orgs.models import Organization, OrganizationMember, Role

from .envelope import ErrorCode

API = Path(__file__).resolve().parent.parent
CONTRACT = json.loads((API / "docs" / "contract.json").read_text("utf-8"))
LARAVEL_ERROR_CODES = API.parent / "laravel" / "app" / "Support" / "ErrorCode.php"


class EnvelopeTests(TestCase):
    def test_health(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual((body["success"], body["data"]), (True, {"status": "ok", "database": "ok"}))
        self.assertRegex(body["meta"]["requestId"], r"^req_[A-Za-z0-9]{16}$")
        self.assertEqual(response["X-Request-Id"], body["meta"]["requestId"])
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_health_when_the_database_is_down(self):
        with mock.patch("common.views.connection.cursor", side_effect=DatabaseError("down")), self.assertLogs("common.views", "ERROR"):
            response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], {"code": "INTERNAL_ERROR", "message": "Service unavailable."})

    def test_the_panels_request_id_is_kept(self):
        response = self.client.get("/api/v1/health", HTTP_X_REQUEST_ID="req_FromThePanel123")
        self.assertEqual(response.json()["meta"]["requestId"], "req_FromThePanel123")
        bad = self.client.get("/api/v1/health", HTTP_X_REQUEST_ID="<script>")
        self.assertNotEqual(bad.json()["meta"]["requestId"], "<script>")

    def test_unknown_paths_answer_in_the_envelope(self):
        response = self.client.get("/api/v1/nope")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")


class ErrorCodeTests(SimpleTestCase):
    # The Laravel reference sits next to this folder in the repo, not inside the Docker image.
    @unittest.skipUnless(LARAVEL_ERROR_CODES.exists(), "Laravel reference not available")
    def test_same_codes_and_statuses_as_laravel(self):
        """The codes are part of the public API: they must match the Laravel reference one for one."""
        php = LARAVEL_ERROR_CODES.read_text("utf-8")
        import re
        laravel_codes = set(re.findall(r"case (\w+) = '\w+';", php))
        self.assertEqual({c.value for c in ErrorCode}, laravel_codes)
        for code, status in [("VALIDATION_ERROR", 422), ("INVALID_API_KEY", 401), ("FEATURE_DISABLED", 403),
                             ("IDEMPOTENCY_CONFLICT", 409), ("INSUFFICIENT_BALANCE", 402), ("PROVIDER_ERROR", 502),
                             ("DAILY_LIMIT_EXCEEDED", 429), ("SERVICE_UNAVAILABLE", 503)]:
            self.assertEqual(ErrorCode(code).status, status, code)


class ProductionGuardTests(SimpleTestCase):
    def check_settings(self, **env):
        base = {k: v for k, v in os.environ.items() if not k.startswith(("POSTGRES_", "SECRET_KEY", "API_KEY", "SETTINGS_", "FRONTEND_"))}
        code = "import django, os; os.environ['DJANGO_SETTINGS_MODULE']='product.settings'; django.setup()"
        return subprocess.run([sys.executable, "-c", code], cwd=API, env=base | {"DEBUG": "False"} | env,
                              capture_output=True, text=True)

    def test_placeholder_secrets_stop_the_site(self):
        result = self.check_settings(SECRET_KEY="change-me")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SECRET_KEY is missing", result.stderr)

    def test_real_secrets_start(self):
        real = "x" * 48
        result = self.check_settings(SECRET_KEY=real, API_KEY_PEPPER=real, SETTINGS_ENCRYPTION_KEY=real, FRONTEND_PROXY_SECRET=real)
        self.assertEqual(result.returncode, 0, result.stderr)


class SchemaTests(TestCase):
    def test_core_records_fit_together(self):
        user = User.objects.create_user("niloy@example.com", "A.I. Niloy")
        self.assertEqual((user.platform_role, user.status, user.locale, user.is_active, user.is_staff), ("USER", "ACTIVE", "en", True, False))
        self.assertFalse(user.has_usable_password())
        org = Organization.objects.create(name="Shop", slug="shop")
        role = Role.objects.create(organization=org, key="owner", name="Owner", is_system=True)
        OrganizationMember.objects.create(organization=org, user=user, role=role, joined_at=org.created_at)
        wallet = Wallet.objects.create(organization=org)
        self.assertEqual((wallet.balance, wallet.currency, wallet.low_balance_threshold), (Decimal("0"), "BDT", Decimal("100")))
        self.assertEqual(org.wallet, wallet)  # one wallet per organisation
        self.assertEqual(list(org.organizationmember_set.values_list("user__email", flat=True)), ["niloy@example.com"])


class ContractTests(SimpleTestCase):
    """docs/contract.json lists every endpoint of the Laravel API. An endpoint is marked done once
    Django answers it and its ported tests pass; this keeps the list honest."""

    def test_contract_is_complete(self):
        self.assertEqual(len(CONTRACT), 248)
        self.assertEqual(len({(e["method"], e["path"]) for e in CONTRACT}), 248)

    def test_done_endpoints_exist(self):
        from django.urls import Resolver404, resolve

        missing = []
        for endpoint in CONTRACT:
            if endpoint["done"]:
                path = "/api" + endpoint["path"].replace("{id}", "00000000-0000-0000-0000-000000000000")
                try:
                    resolve(path)
                except Resolver404:
                    missing.append(f"{endpoint['method']} {endpoint['path']}")
        self.assertEqual(missing, [])
        done = sum(e["done"] for e in CONTRACT)
        print(f"\n[contract] {done} of {len(CONTRACT)} endpoints done", file=sys.stderr)
