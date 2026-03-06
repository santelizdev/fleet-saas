from django.contrib import admin

from config.admin_scoping import CompanyScopedAdminMixin

from .models import ExpenseCategory, VehicleExpense, VehicleExpenseAttachment


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "name", "created_at")
    list_filter = ("company",)
    search_fields = ("name",)
    form_company_filters = {"company": "id"}


@admin.register(VehicleExpense)
class VehicleExpenseAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "vehicle", "amount_clp", "approval_status", "payment_status", "expense_date")
    list_filter = ("company", "approval_status", "payment_status")
    search_fields = ("invoice_number", "supplier", "vehicle__plate")
    form_company_filters = {
        "company": "id",
        "vehicle": "company_id",
        "category": "company_id",
        "reported_by": "company_id",
        "approved_by": "company_id",
        "paid_by": "company_id",
    }


@admin.register(VehicleExpenseAttachment)
class VehicleExpenseAttachmentAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "vehicle_expense", "attachment", "created_at")
    list_filter = ("company",)
    form_company_filters = {
        "company": "id",
        "vehicle_expense": "company_id",
        "attachment": "company_id",
    }
