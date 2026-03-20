from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.accounts.models import User
from apps.companies.models import Company
from apps.documents.models import DriverLicense, VehicleDocument
from apps.vehicles.models import Vehicle


class AlertState(models.TextChoices):
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    ACKNOWLEDGED = "acknowledged", "Acknowledged"
    RESOLVED = "resolved", "Resolved"


class DocumentAlert(models.Model):
    KIND_EXPIRY = "expiry"
    KIND_EXPIRED = "expired"
    KIND_CHOICES = [
        (KIND_EXPIRY, "Expiry"),
        (KIND_EXPIRED, "Expired"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="document_alerts")
    vehicle_document = models.ForeignKey(
        VehicleDocument,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="alerts",
    )
    driver_license = models.ForeignKey(
        DriverLicense,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="alerts",
    )
    kind = models.CharField(max_length=32, choices=KIND_CHOICES, default=KIND_EXPIRY)
    due_date = models.DateField()
    scheduled_for = models.DateField()
    state = models.CharField(max_length=16, choices=AlertState.choices, default=AlertState.PENDING)
    message = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "state", "scheduled_for"]),
            models.Index(fields=["company", "due_date"]),
        ]

    def clean(self):
        has_vehicle_doc = bool(self.vehicle_document_id)
        has_driver_license = bool(self.driver_license_id)
        if has_vehicle_doc == has_driver_license:
            raise ValidationError("DocumentAlert debe apuntar a vehicle_document o driver_license (solo uno).")

        if self.vehicle_document_id and self.vehicle_document.company_id != self.company_id:
            raise ValidationError("vehicle_document debe pertenecer a la misma company.")
        if self.driver_license_id and self.driver_license.company_id != self.company_id:
            raise ValidationError("driver_license debe pertenecer a la misma company.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class MaintenanceAlert(models.Model):
    KIND_BY_DATE = "by_date"
    KIND_BY_KM = "by_km"
    KIND_OVERDUE_DATE = "overdue_date"
    KIND_OVERDUE_KM = "overdue_km"
    KIND_CHOICES = [
        (KIND_BY_DATE, "By date"),
        (KIND_BY_KM, "By km"),
        (KIND_OVERDUE_DATE, "Overdue by date"),
        (KIND_OVERDUE_KM, "Overdue by km"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="maintenance_alerts")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="maintenance_alerts")
    maintenance_record_ref = models.CharField(max_length=64, blank=True, default="")
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    due_date = models.DateField(null=True, blank=True)
    due_km = models.PositiveIntegerField(null=True, blank=True)
    state = models.CharField(max_length=16, choices=AlertState.choices, default=AlertState.PENDING)
    message = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "state"]),
        ]

    def clean(self):
        if self.vehicle.company_id != self.company_id:
            raise ValidationError("vehicle debe pertenecer a la misma company.")
        if self.kind == self.KIND_BY_DATE and self.due_date is None:
            raise ValidationError("MaintenanceAlert by_date requiere due_date.")
        if self.kind == self.KIND_BY_KM and self.due_km is None:
            raise ValidationError("MaintenanceAlert by_km requiere due_km.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Notification(models.Model):
    CHANNEL_EMAIL = "email"
    CHANNEL_IN_APP = "in_app"
    CHANNEL_PUSH = "push"
    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_IN_APP, "In App"),
        (CHANNEL_PUSH, "Push"),
    ]

    STATUS_QUEUED = "queued"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="notifications")
    document_alert = models.ForeignKey(
        DocumentAlert,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    maintenance_alert = models.ForeignKey(
        MaintenanceAlert,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    channel = models.CharField(max_length=16, choices=CHANNEL_CHOICES)
    recipient = models.CharField(max_length=255, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    available_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "status", "available_at"]),
            models.Index(fields=["status", "attempts"]),
        ]

    def clean(self):
        has_doc_alert = bool(self.document_alert_id)
        has_maintenance_alert = bool(self.maintenance_alert_id)
        if has_doc_alert == has_maintenance_alert:
            raise ValidationError("Notification debe estar vinculada a document_alert o maintenance_alert.")

        if self.document_alert_id and self.document_alert.company_id != self.company_id:
            raise ValidationError("document_alert debe pertenecer a la misma company.")
        if self.maintenance_alert_id and self.maintenance_alert.company_id != self.company_id:
            raise ValidationError("maintenance_alert debe pertenecer a la misma company.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def mark_sent(self):
        now = timezone.now()
        self.status = self.STATUS_SENT
        self.sent_at = now
        self.last_error = ""
        self.save(update_fields=["status", "sent_at", "last_error"])

    def mark_failed(self, exc: Exception, max_backoff_minutes: int = 60):
        self.status = self.STATUS_FAILED
        self.attempts += 1
        self.last_error = str(exc)
        backoff_minutes = min(max_backoff_minutes, 2 ** self.attempts)
        self.available_at = timezone.now() + timedelta(minutes=backoff_minutes)
        self.save(update_fields=["status", "attempts", "last_error", "available_at"])


class PushDevice(models.Model):
    """Registro de dispositivos o clientes web habilitados para push por usuario."""

    PROVIDER_WEB = "web"
    PROVIDER_FCM = "fcm"
    PROVIDER_CHOICES = [
        (PROVIDER_WEB, "Web"),
        (PROVIDER_FCM, "Firebase / FCM"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="push_devices")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="push_devices")
    label = models.CharField(max_length=64, blank=True, default="")
    provider = models.CharField(max_length=16, choices=PROVIDER_CHOICES, default=PROVIDER_WEB)
    token = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["company", "token"], name="uniq_push_device_company_token"),
        ]
        indexes = [
            models.Index(fields=["company", "user", "is_active"]),
            models.Index(fields=["company", "provider", "is_active"]),
        ]

    def clean(self):
        if self.user_id and self.company_id and self.user.company_id != self.company_id:
            raise ValidationError("PushDevice.user debe pertenecer a la misma company.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class JobRun(models.Model):
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    job_name = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    details = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["job_name", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]
