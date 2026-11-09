from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("items", views.ItemViewSet, basename="item")
router.register("suppliers", views.SupplierViewSet, basename="supplier")
router.register("prices", views.SupplierPriceViewSet, basename="price")
router.register("transactions", views.TransactionViewSet, basename="transaction")

urlpatterns = router.urls
