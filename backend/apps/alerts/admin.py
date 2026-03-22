"""Admin del centro de alertas con señales visuales de criticidad."""

from __future__ import annotations

from django.contrib import admin
from django.urls import path, reverse
from unfold.admin import ModelAdmin
from unfold.decorators import display

from config.admin_scoping import CompanyScopedAdminMixin

from .admin_views import MessagesOverviewAdminView
from .models import DocumentAlert, JobRun, MaintenanceAlert, Notification


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
    search_fields = ("vehicle__plate", "maintenance_record_ref", "maintenance_record__id", "message")
    list_select_related = ("company", "vehicle", "maintenance_record")
    ordering = ("due_date", "-created_at")
    form_company_filters = {
        "company": "id",
        "vehicle": "company_id",
        "maintenance_record": "company_id",
    }

    @display(description="Estado", label={"pending": "warning", "sent": "info", "acknowledged": "success", "resolved": "success"})
    def state_badge(self, obj):
        return obj.state, obj.get_state_display()


@admin.register(Notification)
class NotificationAdmin(CompanyScopedAdminMixin, ModelAdmin):
    list_display = ("channel_badge", "status_badge", "related_alert", "recipient", "attempts", "available_at", "sent_at")
    list_filter = ("company", "channel", "status")
    search_fields = ("recipient", "last_error", "document_alert__message", "maintenance_alert__message")
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

    def get_urls(self):
        custom_view = self.admin_site.admin_view(MessagesOverviewAdminView.as_view(model_admin=self))
        return [
            path("overview/", custom_view, name="alerts_notification_overview"),
        ] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["messages_overview_url"] = reverse("admin:alerts_notification_overview")
        return super().changelist_view(request, extra_context=extra_context)

    @display(description="Estado", label={"queued": "warning", "sent": "success", "failed": "danger"})
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()

    @display(description="Canal", label={"in_app": "info", "email": "success"})
    def channel_badge(self, obj):
        return obj.channel, obj.get_channel_display()

    @display(description="Origen")
    def related_alert(self, obj):
        if obj.document_alert_id:
            return f"Documento #{obj.document_alert_id}"
        if obj.maintenance_alert_id:
            return f"Mantención #{obj.maintenance_alert_id}"
        return "Sin origen"

    @display(description="Payload")
    def payload_preview(self, obj):
        return obj.payload or {}


@admin.register(JobRun)
class JobRunAdmin(ModelAdmin):
    list_display = ("job_name", "status_badge", "started_at", "finished_at", "created_at")
    list_filter = ("job_name", "status")
    search_fields = ("job_name",)
    ordering = ("-created_at",)

    @display(description="Estado", label={"success": "success", "failed": "danger"})
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()
