from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction

from apps.accounts.permissions import HasCapability
from apps.companies.limits import enforce_upload_limits
from apps.documents.models import (
    Attachment,
    DriverLicense,
    DriverLicenseAttachment,
    VehicleDocument,
    VehicleDocumentAttachment,
)
from apps.vehicles.models import Vehicle
from apps.product_analytics.events import track_event
from apps.documents.services import replace_driver_license_attachment, replace_vehicle_document_attachment

from .serializers import (
    AttachmentSerializer,
    DriverLicenseAttachmentSerializer,
    DriverLicenseRenewSerializer,
    DriverLicenseSerializer,
    VehicleDocumentAttachmentSerializer,
    VehicleDocumentRenewSerializer,
    VehicleDocumentSerializer,
)


class CapabilityScopedViewSet(viewsets.ModelViewSet):
    capability_by_action = {
        "list": "doc.read",
        "retrieve": "doc.read",
        "create": "doc.manage",
        "update": "doc.manage",
        "partial_update": "doc.manage",
        "destroy": "doc.manage",
    }

    def get_permissions(self):
        self.required_capability = self.capability_by_action.get(self.action, "doc.read")
        return [IsAuthenticated(), HasCapability()]

    def _request_company_id(self):
        company_id = getattr(self.request, "company_id", None)
        if company_id is None and getattr(self.request.user, "is_authenticated", False):
            company_id = getattr(self.request.user, "company_id", None)
        return company_id


class AttachmentViewSet(CapabilityScopedViewSet):
    queryset = Attachment.objects.all().order_by("-id")
    serializer_class = AttachmentSerializer

    def get_queryset(self):
        return super().get_queryset().filter(company_id=self._request_company_id())

    def perform_create(self, serializer):
        company_id = self._request_company_id()
        enforce_upload_limits(company_id=company_id, actor_id=self.request.user.id)
        obj = serializer.save(company_id=company_id)
        track_event(company_id=company_id, actor_id=self.request.user.id, event_name="attachment_uploaded", payload={"attachment_id": obj.id})


class VehicleDocumentViewSet(CapabilityScopedViewSet):
    queryset = VehicleDocument.objects.select_related("vehicle", "previous_version").all().order_by("-id")
    serializer_class = VehicleDocumentSerializer

    def get_queryset(self):
        return super().get_queryset().filter(company_id=self._request_company_id())

    def perform_create(self, serializer):
        company_id = self._request_company_id()
        obj = serializer.save(company_id=company_id, created_by=self.request.user)
        track_event(
            company_id=company_id,
            actor_id=self.request.user.id,
            event_name="document_added",
            payload={"document_id": obj.id, "vehicle_id": obj.vehicle_id, "type": obj.type},
        )

    @action(methods=["post"], detail=True, url_path="renew")
    def renew(self, request, pk=None):
        instance = self.get_object()
        serializer = VehicleDocumentRenewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            renewed = instance.renew(
                issue_date=serializer.validated_data["issue_date"],
                expiry_date=serializer.validated_data["expiry_date"],
                notes=serializer.validated_data.get("notes", ""),
                created_by=request.user,
            )
            support_image = serializer.validated_data.get("support_image")
            if support_image:
                replace_vehicle_document_attachment(document=renewed, uploaded_file=support_image, actor_id=request.user.id)
        track_event(
            company_id=instance.company_id,
            actor_id=request.user.id,
            event_name="document_renewed",
            payload={"previous_document_id": instance.id, "new_document_id": renewed.id},
        )
        return Response(self.get_serializer(renewed).data, status=status.HTTP_201_CREATED)

    @action(methods=["post"], detail=False, url_path="create-pack")
    def create_pack(self, request):
        vehicle_id = request.data.get("vehicle_id")
        issue_date = request.data.get("issue_date")
        expiry_date = request.data.get("expiry_date")
        if not vehicle_id or not issue_date or not expiry_date:
            raise ValidationError("vehicle_id, issue_date y expiry_date son obligatorios.")

        company_id = self._request_company_id()
        vehicle = Vehicle.objects.filter(id=vehicle_id, company_id=company_id).first()
        if vehicle is None:
            raise ValidationError("vehicle_id no pertenece a la company autenticada.")
        doc_types = [
            VehicleDocument.TYPE_PERMISO_CIRCULACION,
            VehicleDocument.TYPE_TECNOMECANICA,
            VehicleDocument.TYPE_SEGURO,
            VehicleDocument.TYPE_GASES,
        ]
        created_ids = []
        for doc_type in doc_types:
            obj = VehicleDocument.objects.create(
                company_id=company_id,
                vehicle=vehicle,
                type=doc_type,
                issue_date=issue_date,
                expiry_date=expiry_date,
                reminder_days_before=30,
                notes="created-from-pack",
                created_by=request.user,
            )
            created_ids.append(obj.id)
        return Response({"created_document_ids": created_ids}, status=status.HTTP_201_CREATED)


class VehicleDocumentAttachmentViewSet(CapabilityScopedViewSet):
    queryset = VehicleDocumentAttachment.objects.select_related("vehicle_document", "attachment").all().order_by("-id")
    serializer_class = VehicleDocumentAttachmentSerializer

    def get_queryset(self):
        return super().get_queryset().filter(company_id=self._request_company_id())

    def perform_create(self, serializer):
        company_id = self._request_company_id()
        enforce_upload_limits(company_id=company_id, actor_id=self.request.user.id)
        serializer.save(company_id=company_id)


class DriverLicenseViewSet(CapabilityScopedViewSet):
    queryset = DriverLicense.objects.select_related("driver", "previous_version").all().order_by("-id")
    serializer_class = DriverLicenseSerializer

    def get_queryset(self):
        return super().get_queryset().filter(company_id=self._request_company_id())

    def perform_create(self, serializer):
        company_id = self._request_company_id()
        serializer.save(company_id=company_id, created_by=self.request.user)

    @action(methods=["post"], detail=True, url_path="renew")
    def renew(self, request, pk=None):
        instance = self.get_object()
        serializer = DriverLicenseRenewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            renewed = instance.renew(
                issue_date=serializer.validated_data["issue_date"],
                expiry_date=serializer.validated_data["expiry_date"],
                created_by=request.user,
            )
            support_image = serializer.validated_data.get("support_image")
            if support_image:
                replace_driver_license_attachment(license_doc=renewed, uploaded_file=support_image, actor_id=request.user.id)
        return Response(self.get_serializer(renewed).data, status=status.HTTP_201_CREATED)


class DriverLicenseAttachmentViewSet(CapabilityScopedViewSet):
    queryset = DriverLicenseAttachment.objects.select_related("driver_license", "attachment").all().order_by("-id")
    serializer_class = DriverLicenseAttachmentSerializer

    def get_queryset(self):
        return super().get_queryset().filter(company_id=self._request_company_id())

    def perform_create(self, serializer):
        company_id = self._request_company_id()
        enforce_upload_limits(company_id=company_id, actor_id=self.request.user.id)
        serializer.save(company_id=company_id)
