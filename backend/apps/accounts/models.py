from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)

from apps.companies.models import Company

DRIVER_ROLE_REGEX = r"^(driver|piloto)$"


class UserQuerySet(models.QuerySet):
    """QuerySet base con atajos semánticos para distinguir conductores."""

    def drivers(self):
        return self.filter(user_roles__role__name__iregex=DRIVER_ROLE_REGEX).distinct()

    def non_drivers(self):
        return self.exclude(user_roles__role__name__iregex=DRIVER_ROLE_REGEX).distinct()


class UserManager(BaseUserManager.from_queryset(UserQuerySet)):
    """
    Manager para nuestro usuario custom.
    Usamos email como username (lo más normal en SaaS).
    """

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("El email es obligatorio.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        company_ref = extra_fields.pop("company", None)
        if company_ref is not None and extra_fields.get("company_id") is None:
            if hasattr(company_ref, "id"):
                extra_fields["company_id"] = company_ref.id
            else:
                extra_fields["company_id"] = int(company_ref)

        if extra_fields.get("company_id") is None:
            raise ValueError("Superuser requiere company en este MVP.")

        return self.create_user(email=email, password=password, **extra_fields)



class User(AbstractBaseUser, PermissionsMixin):
    """
    Usuario del sistema.
    En MVP, cada usuario pertenece a una sola empresa (Company).
    Luego se puede permitir que un usuario tenga varias empresas y una active_company.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="users",
    )
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, blank=True, default="")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(
        default=False,
        help_text="Permite acceder al admin de Django.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name", "company"]

    class Meta:
        indexes = [
            models.Index(fields=["company", "email"]),
        ]

    def __str__(self) -> str:
        if self.name:
            return self.name
        return self.email

    def has_driver_role(self) -> bool:
        return self.user_roles.filter(role__name__iregex=DRIVER_ROLE_REGEX).exists()


class Capability(models.Model):
    """
    Permiso atómico. Ejemplos:
    - vehicle.read
    - vehicle.manage
    - doc.manage
    - expense.approve

    Se recomienda que sea global (no por company), para mantener consistencia.
    """

    code = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["code"]),
        ]

    def __str__(self) -> str:
        return self.code


class Role(models.Model):
    """
    Rol dentro de una empresa.
    El rol se define por su set de capabilities.
    Roles típicos: Driver, FleetManager, Admin, etc.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="roles",
    )
    name = models.CharField(max_length=64)
    description = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    capabilities = models.ManyToManyField(
        Capability,
        through="RoleCapability",
        related_name="roles",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"],
                name="uniq_role_company_name",
            )
        ]
        indexes = [
            models.Index(fields=["company", "name"]),
        ]

    def __str__(self) -> str:
        return f"{self.company_id} - {self.name}"


class RoleCapability(models.Model):
    """
    Tabla intermedia: qué capabilities tiene cada rol.
    """

    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    capability = models.ForeignKey(Capability, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["role", "capability"],
                name="uniq_role_capability",
            )
        ]


class UserRole(models.Model):
    """
    Tabla intermedia: qué roles tiene un usuario.
    Permitimos múltiples roles por usuario (más flexible).
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_users")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role"],
                name="uniq_user_role",
            )
        ]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["role"]),
        ]

    def clean(self):
        if self.user_id and self.role_id and self.user.company_id != self.role.company_id:
            raise ValidationError("User y Role deben pertenecer a la misma company.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class DriverManager(UserManager):
    """Manager del proxy Driver para separar operación de conductores."""

    def get_queryset(self):
        return super().get_queryset().drivers()


class Driver(User):
    """
    Proxy operativo de usuario conductor.

    No crea tabla nueva: reutiliza accounts_user pero permite URL/admin propio,
    permisos diferenciados y semántica clara en backoffice.
    """

    objects = DriverManager()

    class Meta:
        proxy = True
        verbose_name = "Conductor"
        verbose_name_plural = "Conductores"
