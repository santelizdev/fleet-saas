from rest_framework import serializers

from apps.documents.models import (
    Attachment,
    DriverLicense,
    DriverLicenseAttachment,
    VehicleDocument,
    VehicleDocumentAttachment,
)


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = [
            "id",
            "company",
            "storage_key",
            "original_name",
            "size_bytes",
            "mime_type",
            "sha256",
            "created_at",
        ]
        read_only_fields = ["id", "company", "created_at"]


class VehicleDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleDocument
        fields = [
            "id",
            "company",
            "vehicle",
            "type",
            "issue_date",
            "expiry_date",
            "reminder_days_before",
            "status",
            "notes",
            "previous_version",
            "is_current",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "company", "status", "is_current", "created_by", "created_at"]


class VehicleDocumentRenewSerializer(serializers.Serializer):
    issue_date = serializers.DateField()
    expiry_date = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class VehicleDocumentAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleDocumentAttachment
        fields = ["id", "company", "vehicle_document", "attachment", "created_at"]
        read_only_fields = ["id", "company", "created_at"]


class DriverLicenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverLicense
        fields = [
            "id",
            "company",
            "driver",
            "license_number",
            "category",
            "issue_date",
            "expiry_date",
            "reminder_days_before",
            "status",
            "previous_version",
            "is_current",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "company", "status", "is_current", "created_by", "created_at"]


class DriverLicenseRenewSerializer(serializers.Serializer):
    issue_date = serializers.DateField()
    expiry_date = serializers.DateField()


class DriverLicenseAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverLicenseAttachment
        fields = ["id", "company", "driver_license", "attachment", "created_at"]
        read_only_fields = ["id", "company", "created_at"]
