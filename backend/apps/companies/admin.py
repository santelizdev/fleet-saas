from django.contrib import admin
from .models import Branch, Company, CompanyLimit
from config.admin_scoping import CompanyScopedAdminMixin


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "rut", "plan", "status", "created_at")
    search_fields = ("name", "rut")
    list_filter = ("status", "plan")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(id=request.user.company_id)


@admin.register(Branch)
class BranchAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "name", "cost_center_code", "created_at")
    search_fields = ("name", "cost_center_code")
    list_filter = ("company",)
    form_company_filters = {
        "company": "id",
    }


@admin.register(CompanyLimit)
class CompanyLimitAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "company",
        "max_vehicles",
        "max_users",
        "max_storage_mb",
        "max_uploads_per_day",
        "max_exports_per_day",
    )
    search_fields = ("company__name", "company__rut")
