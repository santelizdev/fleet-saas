from django.contrib import admin

from config.admin_scoping import CompanyScopedAdminMixin

from .models import DocumentAlert, JobRun, MaintenanceAlert, Notification


@admin.register(DocumentAlert)
class DocumentAlertAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "kind", "state", "scheduled_for", "due_date", "created_at")
    list_filter = ("company", "kind", "state")
    search_fields = ("message",)
    form_company_filters = {
        "company": "id",
        "vehicle_document": "company_id",
        "driver_license": "company_id",
    }


@admin.register(MaintenanceAlert)
class MaintenanceAlertAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "vehicle", "kind", "state", "due_date", "due_km", "created_at")
    list_filter = ("company", "kind", "state")
    search_fields = ("maintenance_record_ref", "message")
    form_company_filters = {
        "company": "id",
        "vehicle": "company_id",
    }


@admin.register(Notification)
class NotificationAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "channel", "status", "attempts", "recipient", "available_at", "sent_at")
    list_filter = ("company", "channel", "status")
    search_fields = ("recipient", "last_error")
    form_company_filters = {
        "company": "id",
        "document_alert": "company_id",
        "maintenance_alert": "company_id",
    }


@admin.register(JobRun)
class JobRunAdmin(admin.ModelAdmin):
    list_display = ("id", "job_name", "status", "started_at", "finished_at", "created_at")
    list_filter = ("job_name", "status")
    search_fields = ("job_name",)
