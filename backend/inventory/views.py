from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError

from accounts.models import Profile
from accounts.permissions import role_required

from .models import Item, Supplier, SupplierPrice, Transaction
from .serializers import (ItemSerializer, SupplierPriceSerializer, SupplierSerializer,
                          TransactionSerializer)
from .stock import replay

ALL_STAFF = role_required(Profile.ROLE_ADMIN, Profile.ROLE_MANAGER, Profile.ROLE_STORE)


class OrgScopedViewSet(viewsets.ModelViewSet):
    """Every query is limited to the caller's own organization (SRS NFR3)."""
    permission_classes = [ALL_STAFF]
    org_field = "organization"

    def _org(self):
        return self.request.user.profile.organization

    def get_queryset(self):
        return super().get_queryset().filter(**{self.org_field: self._org()})

    def perform_create(self, serializer):
        serializer.save(organization=self._org())


class ItemViewSet(OrgScopedViewSet):
    queryset = Item.objects.prefetch_related("transactions")
    serializer_class = ItemSerializer
    http_method_names = ["get", "post", "head", "options"]


class SupplierViewSet(OrgScopedViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    http_method_names = ["get", "post", "head", "options"]


class SupplierPriceViewSet(OrgScopedViewSet):
    queryset = SupplierPrice.objects.select_related("supplier", "item")
    serializer_class = SupplierPriceSerializer
    org_field = "item__organization"
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        item = self.request.query_params.get("item")
        return qs.filter(item_id=item) if item else qs

    def perform_create(self, serializer):
        serializer.save()


class TransactionViewSet(OrgScopedViewSet):
    queryset = Transaction.objects.select_related("item", "supplier")
    serializer_class = TransactionSerializer
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get("item"):
            qs = qs.filter(item_id=params["item"])
        if params.get("kind"):
            qs = qs.filter(kind=params["kind"])
        return qs

    def perform_create(self, serializer):
        serializer.save(organization=self._org(), created_by=self.request.user)

    def perform_destroy(self, instance):
        # Deleting a purchase could make stock negative at an earlier/later point.
        remaining = [(t.date, t.id, t.kind, t.quantity)
                     for t in instance.item.transactions.exclude(pk=instance.pk)]
        if replay(remaining)[1] < 0:
            raise ValidationError({"detail": "Cannot delete: stock would become negative."})
        instance.delete()
