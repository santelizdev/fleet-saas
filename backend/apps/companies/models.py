from django.db import models
from django.utils.translation import gettext_lazy as _


class Company(models.Model):
    """
    Representa un cliente (tenant) dentro del SaaS.
    Todo dato del sistema debe pertenecer a una Company (multiempresa).
    """

    STATUS_ACTIVE = "active"
    STATUS_SUSPENDED = "suspended"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, _("Activa")),
        (STATUS_SUSPENDED, _("Suspendida")),
    ]

    name = models.CharField(max_length=255)
    rut = models.CharField(
        max_length=32,
        unique=True,
        help_text=_("RUT de la empresa. Único en el sistema."),
    )
    plan = models.CharField(
        max_length=64,
        default="trial",
        help_text=_("Nombre del plan. Por ahora sirve para límites internos y futura facturación."),
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("empresa")
        verbose_name_plural = _("empresas")
        indexes = [
            models.Index(fields=["rut"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.rut})"


class Branch(models.Model):
    """
    Sucursal/centro de costo. Es opcional en MVP, pero útil para reportes.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="branches",
    )
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=512, blank=True, default="")
    cost_center_code = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text=_("Código interno del centro de costo (si el cliente lo usa)."),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("sucursal")
        verbose_name_plural = _("sucursales")
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"],
                name="uniq_branch_company_name",
            )
        ]
        indexes = [
            models.Index(fields=["company", "name"]),
        ]

    def __str__(self) -> str:
        return f"{self.company_id} - {self.name}"


class CompanyLimit(models.Model):
    """
    Límites operativos por empresa para proteger el VPS.
    """

    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="limits")
    max_vehicles = models.PositiveIntegerField(default=100)
    max_users = models.PositiveIntegerField(default=50)
    max_storage_mb = models.PositiveIntegerField(default=1024)
    max_uploads_per_day = models.PositiveIntegerField(default=200)
    max_exports_per_day = models.PositiveIntegerField(default=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("membresía")
        verbose_name_plural = _("membresías")

    def __str__(self) -> str:
        return f"limits:{self.company_id}"
