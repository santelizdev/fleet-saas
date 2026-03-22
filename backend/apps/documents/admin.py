"""Admin documental mejorado para operación con badges y previews."""

from __future__ import annotations

from django.contrib import admin
from django.db import transaction
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from config.admin_scoping import CompanyScopedAdminMixin

from .forms import DriverLicenseAdminForm, VehicleDocumentAdminForm
from .models import Attachment, DriverLicense, DriverLicenseAttachment, VehicleDocument, VehicleDocumentAttachment
from .services import replace_driver_license_attachment, replace_vehicle_document_attachment


class InternalAttachmentAdminMixin:
    """Oculta modelos técnicos de adjuntos del menú lateral principal."""

    def has_module_permission(self, request):
        return False

    def get_model_perms(self, request):
        return {}


@admin.register(Attachment)
class AttachmentAdmin(InternalAttachmentAdminMixin, CompanyScopedAdminMixin, ModelAdmin):
    list_display = ("id", "company_column", "storage_key", "mime_type", "size_bytes", "created_at_column")
    search_fields = ("storage_key", "original_name", "mime_type")
    list_filter = ("company", "mime_type")
    form_company_filters = {"company": "id"}

    @display(description=_("Empresa"), ordering="company")
    def company_column(self, obj):
        return obj.company

    @display(description=_("Creado"), ordering="created_at")
    def created_at_column(self, obj):
        return obj.created_at


@admin.register(VehicleDocument)
class VehicleDocumentAdmin(CompanyScopedAdminMixin, ModelAdmin):
    """Organiza documentos del vehículo con foco en vencimientos."""

    form = VehicleDocumentAdminForm
    list_display = ("vehicle_column", "type_column", "status_badge", "is_current_badge", "expiry_date_column", "support_preview_link")
    list_filter = ("company", "type", "status", "is_current", "expiry_date")
    search_fields = ("vehicle__plate", "vehicle__assigned_driver__name", "type", "notes")
    list_select_related = ("company", "vehicle", "vehicle__assigned_driver")
    ordering = ("expiry_date",)
    fields = (
        "company",
        "vehicle",
        "type",
        ("issue_date", "expiry_date"),
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

    @display(description=_("Vehículo"), ordering="vehicle__plate")
    def vehicle_column(self, obj):
        return obj.vehicle

    @display(description=_("Tipo"), ordering="type")
    def type_column(self, obj):
        return obj.get_type_display()

    @display(description=_("Fecha de vencimiento"), ordering="expiry_date")
    def expiry_date_column(self, obj):
        return obj.expiry_date

    @display(
        description="Estado",
        ordering="status",
        label={
            VehicleDocument.STATUS_ACTIVE: "success",
            VehicleDocument.STATUS_REPLACED: "info",
            VehicleDocument.STATUS_EXPIRED: "danger",
        },
    )
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()

    @display(description="Actual")
    def is_current_badge(self, obj):
        tone = "success" if obj.is_current else "info"
        label = "Sí" if obj.is_current else "Histórico"
        return format_html('<span class="fleet-badge fleet-badge-{}">{}</span>', tone, label)

    @display(description=_("Soporte"))
    def support_preview_link(self, obj):
        return "Disponible" if obj.support_attachment else "Sin adjunto"

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
        return format_html('<img src="{}" style="max-width: 240px; max-height: 240px; border-radius: 12px;" />', attachment.file_url)

    support_image_preview.short_description = "Imagen actual"


@admin.register(VehicleDocumentAttachment)
class VehicleDocumentAttachmentAdmin(InternalAttachmentAdminMixin, CompanyScopedAdminMixin, ModelAdmin):
    list_display = ("id", "company_column", "vehicle_document", "attachment", "created_at_column")
    list_filter = ("company",)
    fields = ("company", "vehicle_document", "attachment")
    form_company_filters = {
        "company": "id",
        "vehicle_document": "company_id",
        "attachment": "company_id",
    }

    @display(description=_("Empresa"), ordering="company")
    def company_column(self, obj):
        return obj.company

    @display(description=_("Creado"), ordering="created_at")
    def created_at_column(self, obj):
        return obj.created_at

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "attachment":
            formfield.widget.can_add_related = False
        return formfield


@admin.register(DriverLicense)
class DriverLicenseAdmin(CompanyScopedAdminMixin, ModelAdmin):
    """Agrupa licencias por vigencia y conductor."""

    form = DriverLicenseAdminForm
    list_display = ("driver_column", "license_number_column", "status_badge", "is_current_badge", "expiry_date_column", "support_preview_link")
    list_filter = ("company", "status", "is_current", "expiry_date")
    search_fields = ("driver__name", "driver__email", "license_number", "category")
    list_select_related = ("company", "driver")
    ordering = ("expiry_date",)
    fields = (
        "company",
        "driver",
        "license_number",
        "category",
        ("issue_date", "expiry_date"),
        "reminder_days_before",
        "support_image",
        "support_image_preview",
    )
    readonly_fields = ("support_image_preview",)
    form_company_filters = {
        "company": "id",
        "driver": "company_id",
    }

    @display(description=_("Conductor"), ordering="driver__name")
    def driver_column(self, obj):
        return obj.driver

    @display(description=_("Número de licencia"), ordering="license_number")
    def license_number_column(self, obj):
        return obj.license_number

    @display(description=_("Fecha de vencimiento"), ordering="expiry_date")
    def expiry_date_column(self, obj):
        return obj.expiry_date

    @display(
        description="Estado",
        ordering="status",
        label={
            DriverLicense.STATUS_ACTIVE: "success",
            DriverLicense.STATUS_REPLACED: "info",
            DriverLicense.STATUS_EXPIRED: "danger",
        },
    )
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()

    @display(description="Actual")
    def is_current_badge(self, obj):
        tone = "success" if obj.is_current else "info"
        label = "Sí" if obj.is_current else "Histórico"
        return format_html('<span class="fleet-badge fleet-badge-{}">{}</span>', tone, label)

    @display(description=_("Soporte"))
    def support_preview_link(self, obj):
        return "Disponible" if obj.support_attachment else "Sin adjunto"

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
        return format_html('<img src="{}" style="max-width: 240px; max-height: 240px; border-radius: 12px;" />', attachment.file_url)

    support_image_preview.short_description = "Imagen actual"


@admin.register(DriverLicenseAttachment)
class DriverLicenseAttachmentAdmin(InternalAttachmentAdminMixin, CompanyScopedAdminMixin, ModelAdmin):
    list_display = ("id", "company_column", "driver_license", "attachment", "created_at_column")
    list_filter = ("company",)
    form_company_filters = {
        "company": "id",
        "driver_license": "company_id",
        "attachment": "company_id",
    }

    @display(description=_("Empresa"), ordering="company")
    def company_column(self, obj):
        return obj.company

    @display(description=_("Creado"), ordering="created_at")
    def created_at_column(self, obj):
        return obj.created_at
