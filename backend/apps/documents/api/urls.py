from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AttachmentViewSet,
    DriverLicenseAttachmentViewSet,
    DriverLicenseViewSet,
    VehicleDocumentAttachmentViewSet,
    VehicleDocumentViewSet,
)

router = DefaultRouter()
router.register("attachments", AttachmentViewSet, basename="attachment")
router.register("vehicle-documents", VehicleDocumentViewSet, basename="vehicle-document")
router.register(
    "vehicle-document-attachments",
    VehicleDocumentAttachmentViewSet,
    basename="vehicle-document-attachment",
)
router.register("driver-licenses", DriverLicenseViewSet, basename="driver-license")
router.register(
    "driver-license-attachments",
    DriverLicenseAttachmentViewSet,
    basename="driver-license-attachment",
)

urlpatterns = [
    path("", include(router.urls)),
]
