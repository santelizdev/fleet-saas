from django.db import transaction
from rest_framework import serializers

from apps.documents.models import (
    Attachment,
    DriverLicense,
    DriverLicenseAttachment,
    VehicleDocument,
    VehicleDocumentAttachment,
)
from apps.documents.services import (
    replace_driver_license_attachment,
    replace_vehicle_document_attachment,
    validate_support_image,
)


class AttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.CharField(read_only=True)

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
            "file_url",
            "created_at",
        ]
        read_only_fields = ["id", "company", "created_at"]


class VehicleDocumentSerializer(serializers.ModelSerializer):
    support_image = serializers.ImageField(write_only=True, required=False, allow_null=True)
    support_attachment = AttachmentSerializer(read_only=True)

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
            "is_current",
            "created_by",
            "support_attachment",
            "support_image",
            "created_at",
        ]
        read_only_fields = ["id", "company", "status", "is_current", "created_by", "created_at"]

    def validate_support_image(self, value):
        try:
            validate_support_image(value)
        except Exception as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value

    def create(self, validated_data):
        support_image = validated_data.pop("support_image", None)
        with transaction.atomic():
            instance = super().create(validated_data)
            if support_image:
                request = self.context.get("request")
                replace_vehicle_document_attachment(
                    document=instance,
                    uploaded_file=support_image,
                    actor_id=request.user.id if request else None,
                )
            return instance

    def update(self, instance, validated_data):
        support_image = validated_data.pop("support_image", None)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            if support_image:
                request = self.context.get("request")
                replace_vehicle_document_attachment(
                    document=instance,
                    uploaded_file=support_image,
                    actor_id=request.user.id if request else None,
                )
            return instance


class VehicleDocumentRenewSerializer(serializers.Serializer):
    issue_date = serializers.DateField()
    expiry_date = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    support_image = serializers.ImageField(required=False, allow_null=True)

    def validate_support_image(self, value):
        if value is None:
            return value
        try:
            validate_support_image(value)
        except Exception as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value


class VehicleDocumentAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleDocumentAttachment
        fields = ["id", "company", "vehicle_document", "attachment", "created_at"]
        read_only_fields = ["id", "company", "created_at"]


class DriverLicenseSerializer(serializers.ModelSerializer):
    support_image = serializers.ImageField(write_only=True, required=False, allow_null=True)
    support_attachment = AttachmentSerializer(read_only=True)

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
            "is_current",
            "created_by",
            "support_attachment",
            "support_image",
            "created_at",
        ]
        read_only_fields = ["id", "company", "status", "is_current", "created_by", "created_at"]

    def validate_support_image(self, value):
        try:
            validate_support_image(value)
        except Exception as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value

    def create(self, validated_data):
        support_image = validated_data.pop("support_image", None)
        with transaction.atomic():
            instance = super().create(validated_data)
            if support_image:
                request = self.context.get("request")
                replace_driver_license_attachment(
                    license_doc=instance,
                    uploaded_file=support_image,
                    actor_id=request.user.id if request else None,
                )
            return instance

    def update(self, instance, validated_data):
        support_image = validated_data.pop("support_image", None)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            if support_image:
                request = self.context.get("request")
                replace_driver_license_attachment(
                    license_doc=instance,
                    uploaded_file=support_image,
                    actor_id=request.user.id if request else None,
                )
            return instance


class DriverLicenseRenewSerializer(serializers.Serializer):
    issue_date = serializers.DateField()
    expiry_date = serializers.DateField()
    support_image = serializers.ImageField(required=False, allow_null=True)

    def validate_support_image(self, value):
        if value is None:
            return value
        try:
            validate_support_image(value)
        except Exception as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value


class DriverLicenseAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverLicenseAttachment
        fields = ["id", "company", "driver_license", "attachment", "created_at"]
        read_only_fields = ["id", "company", "created_at"]
