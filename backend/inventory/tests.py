from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import Organization, Profile
from .models import Item, Supplier, Transaction


def make_user(username, org, role=Profile.ROLE_MANAGER):
    user = User.objects.create_user(username, f"{username}@example.com", "Str0ng-Passw0rd!x")
    Profile.objects.create(user=user, organization=org, role=role)
    return user, Token.objects.create(user=user)


class InventoryApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.org = Organization.objects.create(name="Org A")
        self.other = Organization.objects.create(name="Org B")
        self.user, token = make_user("manager_a", self.org)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.item = Item.objects.create(organization=self.org, name="Paper", unit="ream")
        self.supplier = Supplier.objects.create(organization=self.org, name="S1")

    def post_tx(self, **kw):
        data = {"item": self.item.id, "kind": "purchase", "quantity": 100,
                "unit_price": "500.00", "supplier": self.supplier.id, "date": "2026-01-05"}
        data.update(kw)
        return self.client.post("/api/transactions/", data, format="json")

    def stock(self):
        return self.client.get("/api/items/").data[0]["current_stock"]

    def test_purchase_and_consumption_update_stock_in_database(self):
        self.assertEqual(self.post_tx().status_code, 201)
        self.assertEqual(self.post_tx(kind="consumption", quantity=30, unit_price=None,
                                      supplier=None, date="2026-01-10").status_code, 201)
        self.assertEqual(Transaction.objects.filter(item=self.item).count(), 2)
        self.assertEqual(self.stock(), 70)

    def test_inventory_count_sets_stock(self):
        self.post_tx()
        self.post_tx(kind="inventory_count", quantity=40, unit_price=None, supplier=None, date="2026-01-20")
        self.assertEqual(self.stock(), 40)

    def test_validation(self):
        self.assertEqual(self.post_tx(quantity=0).status_code, 400)             # must be >= 1
        self.assertEqual(self.post_tx(unit_price=None).status_code, 400)        # purchase needs a price
        self.assertEqual(self.post_tx(date="2999-01-01").status_code, 400)      # no future dates
        self.assertEqual(self.post_tx(kind="consumption", quantity=5, unit_price=None,
                                      supplier=None).status_code, 400)          # would go negative

    def test_edit_recalculates_stock(self):
        tx_id = self.post_tx().data["id"]
        resp = self.client.patch(f"/api/transactions/{tx_id}/", {"quantity": 250}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.stock(), 250)

    def test_organizations_are_isolated(self):
        foreign = Item.objects.create(organization=self.other, name="Secret")
        self.assertEqual(len(self.client.get("/api/items/").data), 1)
        resp = self.client.post("/api/transactions/", {
            "item": foreign.id, "kind": "purchase", "quantity": 5, "unit_price": "10",
            "date": "2026-01-05"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_requires_login(self):
        self.client.credentials()
        self.assertEqual(self.client.get("/api/items/").status_code, 401)
