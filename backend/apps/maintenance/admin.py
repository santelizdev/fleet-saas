"""Admin de mantenimiento y odómetro con señales visuales operacionales."""

from __future__ import annotations

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from config.admin_scoping import CompanyScopedAdminMixin

from .models import MaintenanceRecord, VehicleOdometerLog


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(CompanyScopedAdminMixin, ModelAdmin):
    """Muestra salud de mantenimiento con foco en próximos vencimientos."""

    list_display = (
        "vehicle_column",
        "type_column",
        "status_badge",
        "service_date_column",
        "odometer_km_column",
        "cost_clp_column",
        "next_due_date_column",
        "next_due_km_column",
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

    @display(description=_("Vehículo"), ordering="vehicle__plate")
    def vehicle_column(self, obj):
        return obj.vehicle

    @display(description=_("Tipo"), ordering="type")
    def type_column(self, obj):
        return obj.get_type_display()

    @display(description=_("Fecha de servicio"), ordering="service_date")
    def service_date_column(self, obj):
        return obj.service_date

    @display(description=_("Kilometraje"), ordering="odometer_km")
    def odometer_km_column(self, obj):
        return obj.odometer_km

    @display(description=_("Costo CLP"), ordering="cost_clp")
    def cost_clp_column(self, obj):
        return obj.cost_clp

    @display(description=_("Próximo vencimiento"), ordering="next_due_date")
    def next_due_date_column(self, obj):
        return obj.next_due_date

    @display(description=_("Próximo km"), ordering="next_due_km")
    def next_due_km_column(self, obj):
        return obj.next_due_km

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

    list_display = ("vehicle_column", "km_column", "source_column", "recorded_by_column", "created_at_column")
    list_filter = ("company", "source", "created_at")
    search_fields = ("vehicle__plate", "note")
    list_select_related = ("company", "vehicle", "recorded_by")
    ordering = ("-created_at",)
    form_company_filters = {
        "company": "id",
        "vehicle": "company_id",
        "recorded_by": "company_id",
    }

    @display(description=_("Vehículo"), ordering="vehicle__plate")
    def vehicle_column(self, obj):
        return obj.vehicle

    @display(description="Km", ordering="km")
    def km_column(self, obj):
        return obj.km

    @display(description=_("Origen"), ordering="source")
    def source_column(self, obj):
        return obj.get_source_display()

    @display(description=_("Registrado por"), ordering="recorded_by__name")
    def recorded_by_column(self, obj):
        return obj.recorded_by

    @display(description=_("Creado"), ordering="created_at")
    def created_at_column(self, obj):
        return obj.created_at
