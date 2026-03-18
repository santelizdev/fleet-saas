from django.contrib import admin
from django.db import transaction
from django.utils.html import format_html

from config.admin_scoping import CompanyScopedAdminMixin

from .forms import DriverLicenseAdminForm, VehicleDocumentAdminForm
from .models import Attachment, DriverLicense, DriverLicenseAttachment, VehicleDocument, VehicleDocumentAttachment
from .services import replace_driver_license_attachment, replace_vehicle_document_attachment


class InternalAttachmentAdminMixin:
    def has_module_permission(self, request):
        return False

    def get_model_perms(self, request):
        return {}


@admin.register(Attachment)
class AttachmentAdmin(InternalAttachmentAdminMixin, CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "storage_key", "mime_type", "size_bytes", "created_at")
    search_fields = ("storage_key", "original_name", "mime_type")
    list_filter = ("company", "mime_type")
    form_company_filters = {"company": "id"}


@admin.register(VehicleDocument)
class VehicleDocumentAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    form = VehicleDocumentAdminForm
    list_display = ("id", "company", "vehicle", "type", "status", "is_current", "expiry_date")
    list_filter = ("company", "type", "status", "is_current")
    search_fields = ("vehicle__plate", "vehicle__assigned_driver__name", "type")
    fields = (
        "company",
        "vehicle",
        "type",
        "issue_date",
        "expiry_date",
        "reminder_days_before",
        "support_image",
        "support_image_preview",
        "notes",
    )
    readonly_fields = ("support_image_preview",)
    form_company_filters = {
        "company": "id",
        "vehicle": "company_id",
    }

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.company_id = request.user.company_id
        if obj.created_by_id is None:
            obj.created_by = request.user
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            support_image = form.cleaned_data.get("support_image")
            if support_image:
                replace_vehicle_document_attachment(document=obj, uploaded_file=support_image, actor_id=request.user.id)

    def support_image_preview(self, obj):
        attachment = getattr(obj, "support_attachment", None)
        if not attachment or not attachment.file_url:
            return "Sin imagen"
        return format_html('<img src="{}" style="max-width: 240px; max-height: 240px;" />', attachment.file_url)

    support_image_preview.short_description = "Imagen actual"


@admin.register(VehicleDocumentAttachment)
class VehicleDocumentAttachmentAdmin(InternalAttachmentAdminMixin, CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "vehicle_document", "attachment", "created_at")
    list_filter = ("company",)
    fields = ("company", "vehicle_document", "attachment")
    form_company_filters = {
        "company": "id",
        "vehicle_document": "company_id",
        "attachment": "company_id",
    }

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "attachment":
            formfield.widget.can_add_related = False
        return formfield


@admin.register(DriverLicense)
class DriverLicenseAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    form = DriverLicenseAdminForm
    list_display = ("id", "company", "driver", "license_number", "status", "is_current", "expiry_date")
    list_filter = ("company", "status", "is_current")
    search_fields = ("driver__name", "driver__email", "license_number")
    fields = (
        "company",
        "driver",
        "license_number",
        "category",
        "issue_date",
        "expiry_date",
        "reminder_days_before",
        "support_image",
        "support_image_preview",
    )
    readonly_fields = ("support_image_preview",)
    form_company_filters = {
        "company": "id",
        "driver": "company_id",
    }

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.company_id = request.user.company_id
        if obj.created_by_id is None:
            obj.created_by = request.user
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            support_image = form.cleaned_data.get("support_image")
            if support_image:
                replace_driver_license_attachment(license_doc=obj, uploaded_file=support_image, actor_id=request.user.id)

    def support_image_preview(self, obj):
        attachment = getattr(obj, "support_attachment", None)
        if not attachment or not attachment.file_url:
            return "Sin imagen"
        return format_html('<img src="{}" style="max-width: 240px; max-height: 240px;" />', attachment.file_url)

    support_image_preview.short_description = "Imagen actual"


@admin.register(DriverLicenseAttachment)
class DriverLicenseAttachmentAdmin(InternalAttachmentAdminMixin, CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "driver_license", "attachment", "created_at")
    list_filter = ("company",)
    form_company_filters = {
        "company": "id",
        "driver_license": "company_id",
        "attachment": "company_id",
    }
