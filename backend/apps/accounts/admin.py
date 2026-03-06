from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User, Role, Capability, RoleCapability, UserRole
from config.admin_scoping import CompanyScopedAdminMixin


@admin.register(User)
class UserAdmin(CompanyScopedAdminMixin, DjangoUserAdmin):
    """
    Admin para el user custom.
    Importante: configuramos fields y list_display para que sea operable.
    """

    ordering = ("email",)
    list_display = ("id", "email", "name", "company", "is_active", "is_staff", "created_at")
    search_fields = ("email", "name")
    list_filter = ("company", "is_active", "is_staff")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal", {"fields": ("name", "phone", "company")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "created_at")}),
    )

    add_fieldsets = (
        (None, {"fields": ("email", "name", "phone", "company", "password1", "password2")}),
    )

    readonly_fields = ("created_at",)
    form_company_filters = {
        "company": "id",
    }


@admin.register(Capability)
class CapabilityAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "description")
    search_fields = ("code", "description")


@admin.register(Role)
class RoleAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "name", "created_at")
    search_fields = ("name",)
    list_filter = ("company",)
    form_company_filters = {
        "company": "id",
    }


@admin.register(RoleCapability)
class RoleCapabilityAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    company_filter_lookup = "role__company_id"
    list_display = ("id", "role", "capability")
    list_filter = ("role__company", "role")
    form_company_filters = {
        "role": "company_id",
    }


@admin.register(UserRole)
class UserRoleAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    company_filter_lookup = "role__company_id"
    list_display = ("id", "user", "role")
    list_filter = ("role__company", "role")
    form_company_filters = {
        "user": "company_id",
        "role": "company_id",
    }
