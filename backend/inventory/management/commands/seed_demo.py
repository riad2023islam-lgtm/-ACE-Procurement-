"""Create a demo organization with simulated history for the live demo.

    python manage.py seed_demo --org "DIU Campus Supershop" \
        --username demo_admin --email demo@example.com --password '<choose one>'

The history is SIMULATED (SRS NFR7 allows simulated test data): 12 full months of
consumption for four items, and only 4 months for "Lab Gloves" so the cold-start
fallback (FR14 / NFR10) can be shown. No credentials are hardcoded; the password
is a required argument.
"""
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Organization, Profile
from inventory.models import Item, Supplier, SupplierPrice, Transaction

# name, unit, monthly base demand, price, months of history, stock today, yearly drift of price
ITEMS = [
    ("A4 Paper Ream", "ream", 450, 520, 12, 180, 0.08),       # shortage: the SRS paper example
    ("Printer Toner", "cartridge", 40, 3200, 12, 55, 0.05),
    ("Whiteboard Marker", "box", 120, 180, 12, 520, -0.03),   # overstock
    ("Floor Cleaner", "litre", 90, 240, 12, 100, 0.00),
    ("Lab Gloves", "box", 60, 450, 4, 30, 0.04),              # cold start: only 4 months
]
SUPPLIERS = [("Meridian Corporate Supply", 2, 1.00),
             ("Dhaka Dealer Traders", 4, 0.97),
             ("CampusMart Wholesale", 3, 1.03)]
DEPARTMENTS = ["CSE", "EEE", "BBA", "Library", "Admin Office"]
SEMESTER_START_MONTHS = {1, 5, 9}


def _add_months(d, n):
    total = d.year * 12 + (d.month - 1) + n
    return date(total // 12, total % 12 + 1, 1)


class Command(BaseCommand):
    help = "Create a demo organization, user and simulated purchase/consumption history."

    def add_arguments(self, parser):
        parser.add_argument("--org", required=True)
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--store-username", help="Also create a store officer (to demo roles).")
        parser.add_argument("--store-password")
        parser.add_argument("--seed", type=int, default=42)

    @transaction.atomic
    def handle(self, *args, **o):
        if Organization.objects.filter(name__iexact=o["org"]).exists():
            raise CommandError("That organization already exists.")
        if User.objects.filter(username__iexact=o["username"]).exists():
            raise CommandError("That username already exists.")
        try:
            validate_password(o["password"], User(username=o["username"], email=o["email"]))
        except ValidationError as exc:
            raise CommandError("Weak password: " + " ".join(exc.messages))

        rng = np.random.default_rng(o["seed"])
        org = Organization.objects.create(name=o["org"])
        admin = User.objects.create_user(o["username"], o["email"], o["password"])
        Profile.objects.create(user=admin, organization=org, role=Profile.ROLE_ADMIN)
        if o.get("store_username") and o.get("store_password"):
            store = User.objects.create_user(o["store_username"], password=o["store_password"])
            Profile.objects.create(user=store, organization=org, role=Profile.ROLE_STORE)

        suppliers = [(Supplier.objects.create(organization=org, name=n, delivery_days=d), f)
                     for n, d, f in SUPPLIERS]

        this_month = date.today().replace(day=1)
        for name, unit, base, price, months, stock_now, drift in ITEMS:
            item = Item.objects.create(organization=org, name=name, unit=unit)
            first = _add_months(this_month, -months)
            # opening stock so the running stock never goes negative
            Transaction.objects.create(organization=org, item=item, kind=Transaction.INVENTORY_COUNT,
                                       quantity=base * 2, date=first, created_by=admin)
            for m in range(months):
                month_start = _add_months(first, m)
                demand = base * (1.0 + 0.012 * m) * (1.3 if month_start.month in SEMESTER_START_MONTHS else 1.0)
                demand = max(int(demand * rng.normal(1.0, 0.07)), 1)
                # purchase on day 1, then consumption spread over the month
                supplier, factor = suppliers[m % len(suppliers)]
                Transaction.objects.create(
                    organization=org, item=item, kind=Transaction.PURCHASE, quantity=demand,
                    unit_price=Decimal(str(round(price * factor, 2))), supplier=supplier,
                    date=month_start, created_by=admin)
                parts = np.diff(np.sort(np.concatenate(([0], rng.integers(1, demand, 3), [demand]))))
                for i, qty in enumerate(parts):
                    if qty < 1:
                        continue
                    Transaction.objects.create(
                        organization=org, item=item, kind=Transaction.CONSUMPTION, quantity=int(qty),
                        department=DEPARTMENTS[(m + i) % len(DEPARTMENTS)],
                        date=month_start + timedelta(days=4 + i * 7), created_by=admin)
            # physical stock-take on the 1st of this month -> current stock
            Transaction.objects.create(organization=org, item=item, kind=Transaction.INVENTORY_COUNT,
                                       quantity=stock_now, date=this_month, created_by=admin)
            # six monthly price points per supplier, drifting over time
            for k in range(6):
                when = _add_months(this_month, -(5 - k))
                trend = 1 + drift * (k / 5)
                for supplier, factor in suppliers:
                    SupplierPrice.objects.create(
                        item=item, supplier=supplier, recorded_on=when,
                        unit_price=Decimal(str(round(price * factor * trend * rng.normal(1.0, 0.005), 2))))

        self.stdout.write(self.style.SUCCESS(
            f"Created '{org.name}' with {Item.objects.filter(organization=org).count()} items. "
            f"Log in as '{o['username']}'."))
