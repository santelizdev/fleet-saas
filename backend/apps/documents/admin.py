from django.contrib import admin

from config.admin_scoping import CompanyScopedAdminMixin

from .models import (
    Attachment,
    DriverLicense,
    DriverLicenseAttachment,
    VehicleDocument,
    VehicleDocumentAttachment,
)


@admin.register(Attachment)
class AttachmentAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "storage_key", "mime_type", "size_bytes", "created_at")
    search_fields = ("storage_key", "original_name", "mime_type")
    list_filter = ("company", "mime_type")
    form_company_filters = {"company": "id"}


@admin.register(VehicleDocument)
class VehicleDocumentAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "vehicle", "type", "status", "is_current", "expiry_date")
    list_filter = ("company", "type", "status", "is_current")
    search_fields = ("vehicle__plate", "type")
    form_company_filters = {
        "company": "id",
        "vehicle": "company_id",
        "created_by": "company_id",
        "previous_version": "company_id",
    }


@admin.register(VehicleDocumentAttachment)
class VehicleDocumentAttachmentAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "vehicle_document", "attachment", "created_at")
    list_filter = ("company",)
    form_company_filters = {
        "company": "id",
        "vehicle_document": "company_id",
        "attachment": "company_id",
    }


@admin.register(DriverLicense)
class DriverLicenseAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "driver", "license_number", "status", "is_current", "expiry_date")
    list_filter = ("company", "status", "is_current")
    search_fields = ("driver__email", "license_number")
    form_company_filters = {
        "company": "id",
        "driver": "company_id",
        "created_by": "company_id",
        "previous_version": "company_id",
    }


@admin.register(DriverLicenseAttachment)
class DriverLicenseAttachmentAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "driver_license", "attachment", "created_at")
    list_filter = ("company",)
    form_company_filters = {
        "company": "id",
        "driver_license": "company_id",
        "attachment": "company_id",
    }
