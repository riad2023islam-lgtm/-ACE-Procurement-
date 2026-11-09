import datetime

from rest_framework import serializers

from .models import Item, Supplier, SupplierPrice, Transaction
from .stock import current_stock, replay


class ItemSerializer(serializers.ModelSerializer):
    current_stock = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = ["id", "name", "unit", "current_stock"]

    def get_current_stock(self, obj):
        return current_stock(obj)

    def validate_name(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("Name is required.")
        org = self.context["request"].user.profile.organization
        qs = Item.objects.filter(organization=org, name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("An item with this name already exists.")
        return value


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["id", "name", "delivery_days"]

    def validate_name(self, value):
        value = " ".join(value.split())
        org = self.context["request"].user.profile.organization
        qs = Supplier.objects.filter(organization=org, name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A supplier with this name already exists.")
        return value


class SupplierPriceSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = SupplierPrice
        fields = ["id", "item", "supplier", "supplier_name", "unit_price", "recorded_on"]

    def validate_unit_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    def validate(self, attrs):
        org = self.context["request"].user.profile.organization
        if attrs["item"].organization_id != org.id or attrs["supplier"].organization_id != org.id:
            raise serializers.ValidationError("Item or supplier does not belong to your organization.")
        return attrs


class TransactionSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default=None)

    class Meta:
        model = Transaction
        fields = ["id", "item", "item_name", "kind", "quantity", "unit_price", "supplier",
                  "supplier_name", "department", "date", "created_at"]
        read_only_fields = ["created_at"]

    def validate_date(self, value):
        if value > datetime.date.today():
            raise serializers.ValidationError("Date cannot be in the future.")
        return value

    def validate_unit_price(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Unit price must be greater than zero.")
        return value

    def validate(self, attrs):
        # On PATCH some fields are missing, so fall back to the stored values.
        inst = self.instance
        get = lambda f: attrs.get(f, getattr(inst, f, None))  # noqa: E731
        org = self.context["request"].user.profile.organization
        item, supplier, kind, qty = get("item"), get("supplier"), get("kind"), get("quantity")

        if item.organization_id != org.id:
            raise serializers.ValidationError({"item": "Item does not belong to your organization."})
        if supplier is not None and supplier.organization_id != org.id:
            raise serializers.ValidationError({"supplier": "Supplier does not belong to your organization."})
        if kind in (Transaction.PURCHASE, Transaction.CONSUMPTION) and qty < 1:
            raise serializers.ValidationError({"quantity": "Quantity must be at least 1."})
        if kind == Transaction.PURCHASE and get("unit_price") is None:
            raise serializers.ValidationError({"unit_price": "Unit price is required for a purchase."})

        # Stock must never go negative once this record is applied (SRS UC-02, 3a).
        others = item.transactions.exclude(pk=inst.pk) if inst else item.transactions.all()
        movements = [(t.date, t.id, t.kind, t.quantity) for t in others]
        movements.append((get("date"), float("inf"), kind, qty))
        _, lowest = replay(movements)
        if lowest < 0:
            raise serializers.ValidationError(
                {"quantity": "Not enough stock: this would make the stock level negative."})
        return attrs
