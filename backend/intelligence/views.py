from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Profile
from accounts.permissions import role_required
from inventory.models import Item

from .services import dashboard_summary, forecast_for_item, recommendation_for_item

# SRS section 3: forecasts and recommendations are for the Manager (and system admin).
MANAGERS = role_required(Profile.ROLE_ADMIN, Profile.ROLE_MANAGER)


class ForecastView(APIView):
    """FR9: GET /api/forecast/?item=<id> -> next-month demand with an error range."""
    permission_classes = [MANAGERS]

    def get(self, request):
        org = request.user.profile.organization
        item_id = request.query_params.get("item")
        if not item_id or not item_id.isdigit():
            return Response({"detail": "Query parameter 'item' (an item id) is required."}, status=400)
        item = get_object_or_404(Item, pk=int(item_id), organization=org)

        history, forecast = forecast_for_item(item)
        if forecast is None:
            return Response(
                {"detail": "No consumption history for this item yet. Enter or import data first."},
                status=404,
            )
        return Response({
            "item": {"id": item.id, "name": item.name, "unit": item.unit},
            "history": [{"month": m.strftime("%Y-%m"), "quantity": q} for m, q in history],
            "forecast": forecast.as_dict(),
        })


class DashboardView(APIView):
    """GET /api/dashboard/ -> KPI cards, demand chart data, risk alerts, recent purchases."""
    permission_classes = [MANAGERS]

    def get(self, request):
        return Response(dashboard_summary(request.user.profile.organization))


class RecommendationListView(APIView):
    """FR11: GET /api/recommendations/ -> one recommendation per item that has history."""
    permission_classes = [MANAGERS]

    def get(self, request):
        org = request.user.profile.organization
        results, skipped = [], []
        for item in Item.objects.filter(organization=org).prefetch_related("transactions"):
            rec = recommendation_for_item(item)
            if rec is None:
                skipped.append(item.name)
            else:
                rec["item_id"] = item.id
                rec["unit"] = item.unit
                results.append(rec)
        order = {"shortage": 0, "ok": 1, "overstock": 2}
        results.sort(key=lambda r: (order[r["risk"]], r["item"]))
        return Response({"recommendations": results, "items_without_history": skipped})
