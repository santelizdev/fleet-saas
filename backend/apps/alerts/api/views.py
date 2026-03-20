from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasCapability
from django.utils import timezone

from apps.alerts.models import AlertState, DocumentAlert, MaintenanceAlert, Notification, PushDevice

from .serializers import DocumentAlertSerializer, MaintenanceAlertSerializer, NotificationSerializer, PushDeviceSerializer


class AlertCapabilityViewSet(viewsets.ModelViewSet):
    capability_by_action = {
        "list": "doc.read",
        "retrieve": "doc.read",
        "create": "doc.manage",
        "update": "doc.manage",
        "partial_update": "doc.manage",
        "destroy": "doc.manage",
        "acknowledge": "doc.manage",
        "resolve": "doc.manage",
        "requeue": "doc.manage",
        "deactivate": "doc.manage",
    }

    def get_permissions(self):
        self.required_capability = self.capability_by_action.get(self.action, "doc.read")
        return [IsAuthenticated(), HasCapability()]

    def _request_company_id(self):
        company_id = getattr(self.request, "company_id", None)
        if company_id is None and getattr(self.request.user, "is_authenticated", False):
            company_id = getattr(self.request.user, "company_id", None)
        return company_id


class DocumentAlertViewSet(AlertCapabilityViewSet):
    queryset = DocumentAlert.objects.select_related("vehicle_document", "driver_license").all().order_by("-id")
    serializer_class = DocumentAlertSerializer

    def get_queryset(self):
        return super().get_queryset().filter(company_id=self._request_company_id())

    def perform_create(self, serializer):
        serializer.save(company_id=self._request_company_id())

    @action(methods=["post"], detail=True)
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        alert.state = AlertState.ACKNOWLEDGED
        alert.save(update_fields=["state"])
        return Response(self.get_serializer(alert).data)

    @action(methods=["post"], detail=True)
    def resolve(self, request, pk=None):
        alert = self.get_object()
        alert.state = AlertState.RESOLVED
        alert.save(update_fields=["state"])
        return Response(self.get_serializer(alert).data)


class MaintenanceAlertViewSet(AlertCapabilityViewSet):
    queryset = MaintenanceAlert.objects.select_related("vehicle").all().order_by("-id")
    serializer_class = MaintenanceAlertSerializer

    def get_queryset(self):
        return super().get_queryset().filter(company_id=self._request_company_id())

    def perform_create(self, serializer):
        serializer.save(company_id=self._request_company_id())

    @action(methods=["post"], detail=True)
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        alert.state = AlertState.ACKNOWLEDGED
        alert.save(update_fields=["state"])
        return Response(self.get_serializer(alert).data)

    @action(methods=["post"], detail=True)
    def resolve(self, request, pk=None):
        alert = self.get_object()
        alert.state = AlertState.RESOLVED
        alert.save(update_fields=["state"])
        return Response(self.get_serializer(alert).data)


class NotificationViewSet(AlertCapabilityViewSet):
    queryset = Notification.objects.select_related("document_alert", "maintenance_alert").all().order_by("-id")
    serializer_class = NotificationSerializer
    http_method_names = ["get", "post", "head", "options", "patch"]

    def get_queryset(self):
        return super().get_queryset().filter(company_id=self._request_company_id())

    def perform_create(self, serializer):
        serializer.save(company_id=self._request_company_id())

    @action(methods=["post"], detail=True)
    def requeue(self, request, pk=None):
        notification = self.get_object()
        notification.status = Notification.STATUS_QUEUED
        notification.last_error = ""
        notification.save(update_fields=["status", "last_error"])
        return Response(self.get_serializer(notification).data, status=status.HTTP_200_OK)


class PushDeviceViewSet(AlertCapabilityViewSet):
    """Permite a clientes registrar tokens web/mobile para notificaciones push."""

    queryset = PushDevice.objects.select_related("user").all().order_by("-last_seen_at", "-id")
    serializer_class = PushDeviceSerializer
    http_method_names = ["get", "post", "head", "options", "patch"]

    def get_queryset(self):
        return super().get_queryset().filter(company_id=self._request_company_id())

    def perform_create(self, serializer):
        serializer.save(company_id=self._request_company_id(), last_seen_at=timezone.now())

    def perform_update(self, serializer):
        serializer.save(last_seen_at=timezone.now())

    @action(methods=["post"], detail=True)
    def deactivate(self, request, pk=None):
        device = self.get_object()
        device.is_active = False
        device.last_seen_at = timezone.now()
        device.save(update_fields=["is_active", "last_seen_at"])
        return Response(self.get_serializer(device).data, status=status.HTTP_200_OK)
