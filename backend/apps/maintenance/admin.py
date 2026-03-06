from django.contrib import admin

from config.admin_scoping import CompanyScopedAdminMixin

from .models import MaintenanceRecord, VehicleOdometerLog


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "company",
        "vehicle",
        "type",
        "status",
        "service_date",
        "odometer_km",
        "cost_clp",
        "next_due_date",
        "next_due_km",
    )
    list_filter = ("company", "type", "status")
    search_fields = ("vehicle__plate", "description")
    form_company_filters = {
        "company": "id",
        "vehicle": "company_id",
        "created_by": "company_id",
    }


@admin.register(VehicleOdometerLog)
class VehicleOdometerLogAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "vehicle", "km", "source", "recorded_by", "created_at")
    list_filter = ("company", "source")
    search_fields = ("vehicle__plate", "note")
    form_company_filters = {
        "company": "id",
        "vehicle": "company_id",
        "recorded_by": "company_id",
    }
