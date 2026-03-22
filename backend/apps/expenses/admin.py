"""Admin de gastos con badges de aprobación/pago y foco analítico."""

from __future__ import annotations

from django.contrib import admin
from django.db import transaction
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from config.admin_scoping import CompanyScopedAdminMixin

from apps.documents.services import replace_vehicle_expense_attachment

from .forms import VehicleExpenseAdminForm
from .models import ExpenseCategory, VehicleExpense, VehicleExpenseAttachment


class InternalAttachmentAdminMixin:
    """Oculta adjuntos técnicos para priorizar la operación del gasto."""

    def has_module_permission(self, request):
        return False

    def get_model_perms(self, request):
        return {}


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(CompanyScopedAdminMixin, ModelAdmin):
    list_display = ("name_column", "company_column", "created_at_column")
    list_filter = ("company",)
    search_fields = ("name",)
    form_company_filters = {"company": "id"}

    def has_module_permission(self, request):
        return request.user.is_superuser

    @display(description=_("Nombre"), ordering="name")
    def name_column(self, obj):
        return obj.name

    @display(description=_("Empresa"), ordering="company")
    def company_column(self, obj):
        return obj.company

    @display(description=_("Creado"), ordering="created_at")
    def created_at_column(self, obj):
        return obj.created_at


@admin.register(VehicleExpense)
class VehicleExpenseAdmin(CompanyScopedAdminMixin, ModelAdmin):
    """Presenta gastos de flota con señales rápidas para finanzas y operación."""

    form = VehicleExpenseAdminForm
    list_display = (
        "expense_date_column",
        "vehicle_column",
        "category_column",
        "amount_clp_column",
        "approval_badge",
        "payment_badge",
        "reported_by_column",
    )
    list_filter = ("company", "expense_date", "category", "approval_status", "payment_status")
    search_fields = ("invoice_number", "supplier", "vehicle__plate", "vehicle__assigned_driver__name")
    list_select_related = ("company", "vehicle", "category", "reported_by", "approved_by", "paid_by")
    ordering = ("-expense_date", "-id")
    fieldsets = (
        ("Contexto", {"fields": ("company", "vehicle", "category")}),
        ("Detalle financiero", {"fields": (("amount_clp", "expense_date"), ("supplier", "invoice_number"), "km")}),
        ("Soporte", {"fields": ("support_image", "support_image_preview", "notes")}),
        ("Workflow", {"fields": (("reported_by", "approved_by", "paid_by"),)}),
    )
    readonly_fields = ("reported_by", "approved_by", "paid_by", "support_image_preview")
    form_company_filters = {
        "company": "id",
        "vehicle": "company_id",
        "category": "company_id",
        "reported_by": "company_id",
        "approved_by": "company_id",
        "paid_by": "company_id",
    }

    @display(description=_("Fecha del gasto"), ordering="expense_date")
    def expense_date_column(self, obj):
        return obj.expense_date

    @display(description=_("Vehículo"), ordering="vehicle__plate")
    def vehicle_column(self, obj):
        return obj.vehicle

    @display(description=_("Categoría"), ordering="category__name")
    def category_column(self, obj):
        return obj.category or "Sin categoría"

    @display(description=_("Monto CLP"), ordering="amount_clp")
    def amount_clp_column(self, obj):
        return obj.amount_clp

    @display(description=_("Reportado por"), ordering="reported_by__name")
    def reported_by_column(self, obj):
        return obj.reported_by

    @display(
        description="Aprobación",
        label={
            VehicleExpense.APPROVAL_REPORTED: "warning",
            VehicleExpense.APPROVAL_APPROVED: "success",
            VehicleExpense.APPROVAL_REJECTED: "danger",
        },
    )
    def approval_badge(self, obj):
        return obj.approval_status, obj.get_approval_status_display()

    @display(
        description="Pago",
        label={
            VehicleExpense.PAYMENT_UNPAID: "warning",
            VehicleExpense.PAYMENT_PAID: "success",
        },
    )
    def payment_badge(self, obj):
        return obj.payment_status, obj.get_payment_status_display()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.company_id = request.user.company_id
        if obj.reported_by_id is None:
            obj.reported_by = request.user
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            support_image = form.cleaned_data.get("support_image")
            if support_image:
                replace_vehicle_expense_attachment(expense=obj, uploaded_file=support_image, actor_id=request.user.id)

    def support_image_preview(self, obj):
        attachment = getattr(obj, "support_attachment", None)
        if not attachment or not attachment.file_url:
            return "Sin imagen"
        return format_html('<img src="{}" style="max-width: 240px; max-height: 240px; border-radius: 12px;" />', attachment.file_url)

    support_image_preview.short_description = "Imagen actual"


@admin.register(VehicleExpenseAttachment)
class VehicleExpenseAttachmentAdmin(InternalAttachmentAdminMixin, CompanyScopedAdminMixin, ModelAdmin):
    list_display = ("id", "company", "vehicle_expense", "attachment", "created_at")
    list_filter = ("company",)
    form_company_filters = {
        "company": "id",
        "vehicle_expense": "company_id",
        "attachment": "company_id",
    }
