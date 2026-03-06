from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ExpenseCategoryViewSet, VehicleExpenseAttachmentViewSet, VehicleExpenseViewSet

router = DefaultRouter()
router.register("categories", ExpenseCategoryViewSet, basename="expense-category")
router.register("vehicle-expenses", VehicleExpenseViewSet, basename="vehicle-expense")
router.register("vehicle-expense-attachments", VehicleExpenseAttachmentViewSet, basename="vehicle-expense-attachment")

urlpatterns = [
    path("", include(router.urls)),
]
