"""Admin de mantenimiento y odómetro con señales visuales operacionales."""

from __future__ import annotations

from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.decorators import display

from config.admin_scoping import CompanyScopedAdminMixin

from .models import MaintenanceRecord, VehicleOdometerLog


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(CompanyScopedAdminMixin, ModelAdmin):
    """Muestra salud de mantenimiento con foco en próximos vencimientos."""

    list_display = (
        "vehicle",
        "type",
        "status_badge",
        "service_date",
        "odometer_km",
        "cost_clp",
        "next_due_date",
        "next_due_km",
    )
    list_filter = ("company", "type", "status", "service_date")
    search_fields = ("vehicle__plate", "description")
    list_select_related = ("company", "vehicle", "created_by")
    ordering = ("-service_date",)
    fieldsets = (
        ("Contexto", {"fields": ("company", "vehicle", ("type", "status"))}),
        ("Servicio", {"fields": ("description", ("service_date", "odometer_km"), "cost_clp")}),
        ("Próximo control", {"fields": (("next_due_date", "next_due_km"), "created_by")}),
    )
    form_company_filters = {
        "company": "id",
        "vehicle": "company_id",
        "created_by": "company_id",
    }

    @display(
        description="Estado",
        label={
            MaintenanceRecord.STATUS_OPEN: "warning",
            MaintenanceRecord.STATUS_COMPLETED: "success",
            MaintenanceRecord.STATUS_CANCELLED: "danger",
        },
    )
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()


@admin.register(VehicleOdometerLog)
class VehicleOdometerLogAdmin(CompanyScopedAdminMixin, ModelAdmin):
    """Lista lecturas de kilometraje para trazabilidad operacional."""

    list_display = ("vehicle", "km", "source", "recorded_by", "created_at")
    list_filter = ("company", "source", "created_at")
    search_fields = ("vehicle__plate", "note")
    list_select_related = ("company", "vehicle", "recorded_by")
    ordering = ("-created_at",)
    form_company_filters = {
        "company": "id",
        "vehicle": "company_id",
        "recorded_by": "company_id",
    }
