from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DocumentAlertViewSet, MaintenanceAlertViewSet, NotificationViewSet

router = DefaultRouter()
router.register("document-alerts", DocumentAlertViewSet, basename="document-alert")
router.register("maintenance-alerts", MaintenanceAlertViewSet, basename="maintenance-alert")
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("", include(router.urls)),
]
