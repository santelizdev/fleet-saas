from rest_framework import serializers

from apps.alerts.models import DocumentAlert, MaintenanceAlert, Notification


class DocumentAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentAlert
        fields = [
            "id",
            "company",
            "vehicle_document",
            "driver_license",
            "kind",
            "due_date",
            "scheduled_for",
            "state",
            "message",
            "created_at",
        ]
        read_only_fields = ["id", "company", "created_at"]


class MaintenanceAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceAlert
        fields = [
            "id",
            "company",
            "vehicle",
            "maintenance_record",
            "maintenance_record_ref",
            "kind",
            "due_date",
            "due_km",
            "state",
            "message",
            "created_at",
        ]
        read_only_fields = ["id", "company", "created_at"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "company",
            "document_alert",
            "maintenance_alert",
            "channel",
            "recipient",
            "payload",
            "status",
            "attempts",
            "last_error",
            "available_at",
            "sent_at",
            "created_at",
        ]
        read_only_fields = ["id", "company", "attempts", "last_error", "sent_at", "created_at"]
