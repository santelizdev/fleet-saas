"""Admin del centro de alertas con señales visuales de criticidad."""

from __future__ import annotations

from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.decorators import display

from config.admin_scoping import CompanyScopedAdminMixin

from .models import DocumentAlert, JobRun, MaintenanceAlert, Notification, PushDevice


@admin.register(DocumentAlert)
class DocumentAlertAdmin(CompanyScopedAdminMixin, ModelAdmin):
    list_display = ("kind", "state_badge", "scheduled_for", "due_date", "linked_object")
    list_filter = ("company", "kind", "state", "scheduled_for")
    search_fields = ("message", "vehicle_document__vehicle__plate", "driver_license__driver__name")
    list_select_related = ("company", "vehicle_document", "driver_license")
    ordering = ("scheduled_for",)
    form_company_filters = {
        "company": "id",
        "vehicle_document": "company_id",
        "driver_license": "company_id",
    }

    @display(description="Estado", label={"pending": "warning", "sent": "info", "acknowledged": "success", "resolved": "success"})
    def state_badge(self, obj):
        return obj.state, obj.get_state_display()

    @display(description="Origen")
    def linked_object(self, obj):
        if obj.vehicle_document_id:
            return obj.vehicle_document.vehicle.plate
        if obj.driver_license_id:
            return obj.driver_license.driver.name
        return "Sin vínculo"


@admin.register(MaintenanceAlert)
class MaintenanceAlertAdmin(CompanyScopedAdminMixin, ModelAdmin):
    list_display = ("vehicle", "kind", "state_badge", "due_date", "due_km", "created_at")
    list_filter = ("company", "kind", "state")
    search_fields = ("vehicle__plate", "maintenance_record_ref", "message")
    list_select_related = ("company", "vehicle")
    ordering = ("due_date", "-created_at")
    form_company_filters = {
        "company": "id",
        "vehicle": "company_id",
    }

    @display(description="Estado", label={"pending": "warning", "sent": "info", "acknowledged": "success", "resolved": "success"})
    def state_badge(self, obj):
        return obj.state, obj.get_state_display()


@admin.register(Notification)
class NotificationAdmin(CompanyScopedAdminMixin, ModelAdmin):
    list_display = ("channel", "status_badge", "recipient", "attempts", "available_at", "sent_at")
    list_filter = ("company", "channel", "status")
    search_fields = ("recipient", "last_error")
    list_select_related = ("company", "document_alert", "maintenance_alert")
    ordering = ("-created_at",)
    readonly_fields = ("payload_preview",)
    fields = (
        "company",
        "document_alert",
        "maintenance_alert",
        ("channel", "status"),
        "recipient",
        "payload_preview",
        ("attempts", "available_at", "sent_at"),
        "last_error",
    )
    form_company_filters = {
        "company": "id",
        "document_alert": "company_id",
        "maintenance_alert": "company_id",
    }

    @display(description="Estado", label={"queued": "warning", "sent": "success", "failed": "danger"})
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()

    @display(description="Payload")
    def payload_preview(self, obj):
        return obj.payload or {}


@admin.register(PushDevice)
class PushDeviceAdmin(CompanyScopedAdminMixin, ModelAdmin):
    """Permite registrar tokens push por usuario sin acoplar el admin a un proveedor."""

    list_display = ("user", "provider", "label", "active_badge", "last_seen_at", "created_at")
    list_filter = ("company", "provider", "is_active")
    search_fields = ("user__email", "user__name", "label", "token")
    list_select_related = ("company", "user")
    readonly_fields = ("last_seen_at", "created_at")
    form_company_filters = {
        "company": "id",
        "user": "company_id",
    }

    @display(description="Estado", label={True: "success", False: "danger"})
    def active_badge(self, obj):
        return obj.is_active, "Activo" if obj.is_active else "Inactivo"


@admin.register(JobRun)
class JobRunAdmin(ModelAdmin):
    list_display = ("job_name", "status_badge", "started_at", "finished_at", "created_at")
    list_filter = ("job_name", "status")
    search_fields = ("job_name",)
    ordering = ("-created_at",)

    @display(description="Estado", label={"success": "success", "failed": "danger"})
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()
