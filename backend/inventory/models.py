from django.contrib.auth.models import User
from django.db import models

from accounts.models import Organization


class Item(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=120)
    unit = models.CharField(max_length=30, default="pcs")

    class Meta:
        unique_together = ("organization", "name")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Supplier(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="suppliers")
    name = models.CharField(max_length=120)
    delivery_days = models.PositiveIntegerField(default=3)

    class Meta:
        unique_together = ("organization", "name")
        ordering = ["name"]

    def __str__(self):
        return self.name


class SupplierPrice(models.Model):
    """Price of an item from a supplier on a date (used for price trend and supplier choice)."""
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="prices")
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="prices")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    recorded_on = models.DateField()

    class Meta:
        ordering = ["recorded_on", "id"]


class Transaction(models.Model):
    """One stock movement (SRS FR3).

    PURCHASE         adds `quantity` to stock
    CONSUMPTION      removes `quantity` from stock
    INVENTORY_COUNT  sets stock to `quantity` (a physical stock-take)
    Stock is always derived from these rows (see inventory.stock), so editing or
    deleting a record can never leave a stale stock number behind.
    """
    PURCHASE = "purchase"
    CONSUMPTION = "consumption"
    INVENTORY_COUNT = "inventory_count"
    KIND_CHOICES = [
        (PURCHASE, "Purchase"),
        (CONSUMPTION, "Consumption"),
        (INVENTORY_COUNT, "Inventory count"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="transactions")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="transactions")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.SET_NULL)
    department = models.CharField(max_length=80, blank=True)
    date = models.DateField()
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
