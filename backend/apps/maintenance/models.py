from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction

from apps.companies.models import Company
from apps.vehicles.models import Vehicle


class MaintenanceRecord(models.Model):
    TYPE_PREVENTIVE = "preventive"
    TYPE_CORRECTIVE = "corrective"
    TYPE_CHOICES = [
        (TYPE_PREVENTIVE, "Preventive"),
        (TYPE_CORRECTIVE, "Corrective"),
    ]

    STATUS_OPEN = "open"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="maintenance_records")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="maintenance_records")
    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN)
    description = models.CharField(max_length=255, blank=True, default="")
    service_date = models.DateField()
    odometer_km = models.PositiveIntegerField(default=0)
    cost_clp = models.PositiveIntegerField(default=0)
    next_due_date = models.DateField(null=True, blank=True)
    next_due_km = models.PositiveIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_maintenance_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "vehicle", "service_date"]),
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "next_due_date"]),
            models.Index(fields=["company", "next_due_km"]),
        ]

    def clean(self):
        if self.vehicle_id and self.company_id and self.vehicle.company_id != self.company_id:
            raise ValidationError("Vehicle y MaintenanceRecord deben pertenecer a la misma company.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class VehicleOdometerLog(models.Model):
    SOURCE_MANUAL = "manual"
    SOURCE_EXPENSE = "expense"
    SOURCE_MAINTENANCE = "maintenance"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_EXPENSE, "Expense"),
        (SOURCE_MAINTENANCE, "Maintenance"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="odometer_logs")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="odometer_logs")
    km = models.PositiveIntegerField()
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_odometer_logs",
    )
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "vehicle", "created_at"]),
            models.Index(fields=["company", "vehicle", "km"]),
        ]

    def clean(self):
        if self.vehicle_id and self.company_id and self.vehicle.company_id != self.company_id:
            raise ValidationError("Vehicle y OdometerLog deben pertenecer a la misma company.")

    @transaction.atomic
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        vehicle = self.vehicle
        if self.km > vehicle.current_km:
            vehicle.current_km = self.km
            vehicle.save(update_fields=["current_km"])
