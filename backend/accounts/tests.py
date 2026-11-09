from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APITestCase

from .models import Organization

STRONG = "Str0ng-Passw0rd!x"


class AuthTests(APITestCase):
    def setUp(self):
        cache.clear()   # reset the rate-limit counters between tests

    def register(self, **overrides):
        data = {
            "organization_name": "Test University",
            "username": "alice",
            "email": "alice@example.com",
            "password": STRONG,
            "password2": STRONG,
        }
        data.update(overrides)
        return self.client.post("/api/auth/register/", data, format="json")

    def test_register_creates_org_admin_and_hashes_password(self):
        resp = self.register()
        self.assertEqual(resp.status_code, 201)
        self.assertIn("token", resp.data)
        self.assertEqual(resp.data["user"]["role"], "admin")
        user = User.objects.get(username="alice")
        self.assertNotEqual(user.password, STRONG)           # never stored in plain text
        self.assertTrue(user.password.startswith("pbkdf2_"))
        self.assertTrue(user.check_password(STRONG))

    def test_weak_and_mismatched_passwords_rejected(self):
        self.assertEqual(self.register(password="12345678", password2="12345678").status_code, 400)
        self.assertEqual(self.register(password2="different-Passw0rd!").status_code, 400)

    def test_invalid_email_and_duplicates_rejected(self):
        self.assertEqual(self.register(email="not-an-email").status_code, 400)
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.register(organization_name="test university", username="bob",
                                       email="bob@example.com").status_code, 400)
        self.assertEqual(self.register(organization_name="Other Uni").status_code, 400)  # same username

    def test_login_success_and_failure(self):
        self.register()
        ok = self.client.post("/api/auth/login/", {"username": "alice", "password": STRONG}, format="json")
        self.assertEqual(ok.status_code, 200)
        self.assertIn("token", ok.data)
        bad = self.client.post("/api/auth/login/", {"username": "alice", "password": "wrong"}, format="json")
        self.assertEqual(bad.status_code, 401)
        missing = self.client.post("/api/auth/login/", {"username": "alice"}, format="json")
        self.assertEqual(missing.status_code, 400)

    def test_me_requires_token(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        token = self.register().data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)

    def test_admin_can_add_staff_only_in_own_org(self):
        token = self.register().data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        resp = self.client.post("/api/auth/users/", {
            "username": "store1", "email": "s1@example.com", "password": STRONG, "role": "store_officer",
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Organization.objects.get(name="Test University").members.count(), 2)
