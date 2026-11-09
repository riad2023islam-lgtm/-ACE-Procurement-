from datetime import date

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import Organization, Profile
from inventory.models import Item, Supplier, SupplierPrice, Transaction


def _months_back(n):
    total = date.today().year * 12 + date.today().month - 1 - n
    return date(total // 12, total % 12 + 1, 5)


class IntelligenceApiTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org A")
        self.manager, self.token = self._user("mgr", Profile.ROLE_MANAGER)
        self.store, self.store_token = self._user("store", Profile.ROLE_STORE)
        self.item = Item.objects.create(organization=self.org, name="Paper", unit="ream")
        sup = Supplier.objects.create(organization=self.org, name="S1", delivery_days=2)
        Transaction.objects.create(organization=self.org, item=self.item, kind="inventory_count",
                                   quantity=5000, date=_months_back(10))
        for i, qty in enumerate([420, 450, 470, 620, 680, 500, 480, 520]):
            Transaction.objects.create(organization=self.org, item=self.item, kind="consumption",
                                       quantity=qty, date=_months_back(8 - i))
        Transaction.objects.create(organization=self.org, item=self.item, kind="inventory_count",
                                   quantity=180, date=date.today())
        SupplierPrice.objects.create(item=self.item, supplier=sup, unit_price="500", recorded_on=_months_back(2))
        SupplierPrice.objects.create(item=self.item, supplier=sup, unit_price="520", recorded_on=_months_back(0))

    def _user(self, username, role):
        user = User.objects.create_user(username, f"{username}@example.com", "Str0ng-Passw0rd!x")
        Profile.objects.create(user=user, organization=self.org, role=role)
        return user, Token.objects.create(user=user)

    def auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_forecast_reads_database_history(self):
        self.auth(self.token)
        resp = self.client.get(f"/api/forecast/?item={self.item.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["history"]), 8)
        self.assertGreater(resp.data["forecast"]["forecast"], 0)
        self.assertLessEqual(resp.data["forecast"]["lower"], resp.data["forecast"]["upper"])

    def test_forecast_without_data_returns_404(self):
        empty = Item.objects.create(organization=self.org, name="Empty")
        self.auth(self.token)
        self.assertEqual(self.client.get(f"/api/forecast/?item={empty.id}").status_code, 404)

    def test_recommendation_uses_stock_and_supplier(self):
        self.auth(self.token)
        resp = self.client.get("/api/recommendations/")
        self.assertEqual(resp.status_code, 200)
        rec = resp.data["recommendations"][0]
        self.assertEqual(rec["current_stock"], 180)
        self.assertEqual(rec["supplier"]["name"], "S1")
        self.assertGreater(rec["recommended_quantity"], 0)
        self.assertTrue(rec["reasoning"])

    def test_dashboard_summary(self):
        self.auth(self.token)
        resp = self.client.get("/api/dashboard/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["kpis"]["items_tracked"], 1)
        self.assertTrue(resp.data["demand"]["actual"])
        self.assertGreater(resp.data["demand"]["next_month"]["forecast"], 0)
        self.auth(self.store_token)
        self.assertEqual(self.client.get("/api/dashboard/").status_code, 403)

    def test_store_officer_cannot_see_forecasts(self):
        self.auth(self.store_token)
        self.assertEqual(self.client.get("/api/recommendations/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/forecast/?item={self.item.id}").status_code, 403)
