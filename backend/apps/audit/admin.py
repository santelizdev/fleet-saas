from django.contrib import admin
from .models import AuditLog
from config.admin_scoping import CompanyScopedAdminMixin


@admin.register(AuditLog)
class AuditLogAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "created_at", "company", "actor", "action", "object_type", "object_id")
    list_filter = ("company", "action", "object_type")
    search_fields = ("action", "object_type", "object_id", "actor__email")
    readonly_fields = ("company", "actor", "action", "object_type", "object_id", "before_json", "after_json", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
