from django.contrib import admin
from django.db import transaction
from django.utils.html import format_html

from config.admin_scoping import CompanyScopedAdminMixin

from apps.documents.services import replace_vehicle_expense_attachment

from .forms import VehicleExpenseAdminForm
from .models import ExpenseCategory, VehicleExpense, VehicleExpenseAttachment


class InternalAttachmentAdminMixin:
    def has_module_permission(self, request):
        return False

    def get_model_perms(self, request):
        return {}


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "name", "created_at")
    list_filter = ("company",)
    search_fields = ("name",)
    form_company_filters = {"company": "id"}

    def has_module_permission(self, request):
        return request.user.is_superuser


@admin.register(VehicleExpense)
class VehicleExpenseAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    form = VehicleExpenseAdminForm
    list_display = ("id", "company", "vehicle", "amount_clp", "expense_date", "reported_by")
    list_filter = ("company", "expense_date")
    search_fields = ("invoice_number", "supplier", "vehicle__plate", "vehicle__assigned_driver__name")
    fields = (
        "company",
        "vehicle",
        "category",
        "amount_clp",
        "expense_date",
        "supplier",
        "km",
        "invoice_number",
        "support_image",
        "support_image_preview",
        "notes",
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
        return format_html('<img src="{}" style="max-width: 240px; max-height: 240px;" />', attachment.file_url)

    support_image_preview.short_description = "Imagen actual"


@admin.register(VehicleExpenseAttachment)
class VehicleExpenseAttachmentAdmin(InternalAttachmentAdminMixin, CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "vehicle_expense", "attachment", "created_at")
    list_filter = ("company",)
    form_company_filters = {
        "company": "id",
        "vehicle_expense": "company_id",
        "attachment": "company_id",
    }
