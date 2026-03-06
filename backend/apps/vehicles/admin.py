from django.contrib import admin
from .models import Vehicle
from config.admin_scoping import CompanyScopedAdminMixin


@admin.register(Vehicle)
class VehicleAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "plate", "status", "assigned_driver", "current_km", "created_at")
    search_fields = ("plate", "brand", "model")
    list_filter = ("company", "status")
    form_company_filters = {
        "company": "id",
        "branch": "company_id",
        "assigned_driver": "company_id",
    }
