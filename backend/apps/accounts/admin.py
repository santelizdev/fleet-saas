"""Admin de cuentas y RBAC con estructura más clara para backoffice SaaS."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from unfold.admin import ModelAdmin
from unfold.decorators import display

from config.admin_scoping import CompanyScopedAdminMixin

from .forms import UserAdminChangeForm, UserAdminCreationForm
from .models import Capability, Driver, Role, RoleCapability, User, UserRole


def _ensure_driver_role(user: User):
    """
    Garantiza que un conductor creado desde su módulo quede clasificado como tal.

    Reutiliza rol Driver/Piloto si existe; si no, crea Driver con capabilities
    mínimas para mantener el flujo operativo del MVP.
    """

    driver_role = Role.objects.filter(company=user.company, name__iregex=r"^(driver|piloto)$").order_by("name").first()
    if driver_role is None:
        driver_role = Role.objects.create(company=user.company, name="Driver", description="Rol operativo de conductor")
        for code in ("vehicle.read", "doc.read", "expense.report"):
            capability = Capability.objects.filter(code=code).first()
            if capability:
                RoleCapability.objects.get_or_create(role=driver_role, capability=capability)

    UserRole.objects.get_or_create(user=user, role=driver_role)


class BaseFleetUserAdmin(CompanyScopedAdminMixin, ModelAdmin, DjangoUserAdmin):
    """Base visual/operativa compartida entre usuarios internos y conductores."""

    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    compressed_fields = True
    ordering = ("email",)
    list_display = ("email", "name", "company", "active_badge", "is_staff", "created_at")
    search_fields = ("email", "name", "phone")
    list_filter = ("company", "is_active", "is_staff")
    list_select_related = ("company",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Perfil", {"fields": (("name", "phone"), "company")}),
        (
            "Permisos de acceso",
            {
                "fields": (
                    ("is_active", "is_staff", "is_superuser"),
                    ("groups", "user_permissions"),
                )
            },
        ),
        ("Auditoría", {"fields": ("last_login", "created_at")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    ("name", "phone"),
                    ("company", "is_active", "is_staff"),
                    ("password1", "password2"),
                ),
            },
        ),
    )

    readonly_fields = ("created_at",)
    form_company_filters = {
        "company": "id",
    }

    @display(description="Activo", label={True: "success", False: "danger"})
    def active_badge(self, obj):
        return obj.is_active, "Activo" if obj.is_active else "Inactivo"

@admin.register(User)
class UserAdmin(BaseFleetUserAdmin):
    """Admin de usuarios internos del sistema, excluyendo conductores operativos."""

    def get_queryset(self, request):
        return super().get_queryset(request).non_drivers()


@admin.register(Driver)
class DriverAdmin(BaseFleetUserAdmin):
    """Admin operativo separado para conductores/pilotos."""

    def get_queryset(self, request):
        return super().get_queryset(request).drivers()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        _ensure_driver_role(obj)


@admin.register(Capability)
class CapabilityAdmin(admin.ModelAdmin):
    list_display = ("code", "description")
    search_fields = ("code", "description")


@admin.register(Role)
class RoleAdmin(CompanyScopedAdminMixin, ModelAdmin):
    list_display = ("name", "company", "created_at")
    search_fields = ("name", "description")
    list_filter = ("company",)
    list_select_related = ("company",)
    form_company_filters = {
        "company": "id",
    }


@admin.register(RoleCapability)
class RoleCapabilityAdmin(CompanyScopedAdminMixin, ModelAdmin):
    company_filter_lookup = "role__company_id"
    list_display = ("role", "capability")
    list_filter = ("role__company", "role")
    list_select_related = ("role", "capability")
    form_company_filters = {
        "role": "company_id",
    }


@admin.register(UserRole)
class UserRoleAdmin(CompanyScopedAdminMixin, ModelAdmin):
    company_filter_lookup = "role__company_id"
    list_display = ("user", "role")
    list_filter = ("role__company", "role")
    list_select_related = ("user", "role")
    form_company_filters = {
        "user": "company_id",
        "role": "company_id",
    }
