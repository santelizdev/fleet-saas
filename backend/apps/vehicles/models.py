from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.companies.models import Company, Branch
from apps.accounts.models import User


class Vehicle(models.Model):
    """
    Vehículo administrado por la empresa.
    El assigned_driver es el piloto responsable (puede ser null).
    """

    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, _("Activo")),
        (STATUS_INACTIVE, _("Inactivo")),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="vehicles",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicles",
    )
    plate = models.CharField(
        max_length=16,
        help_text=_("Patente. Única por empresa."),
    )
    brand = models.CharField(max_length=64, blank=True, default="")
    model = models.CharField(max_length=64, blank=True, default="")
    year = models.PositiveIntegerField(null=True, blank=True)
    vin = models.CharField(max_length=64, blank=True, default="")
    engine_number = models.CharField(max_length=64, blank=True, default="")
    current_km = models.PositiveIntegerField(default=0)

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    assigned_driver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_vehicles",
        help_text=_("Piloto responsable (si aplica)."),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("vehículo")
        verbose_name_plural = _("vehículos")
        constraints = [
            models.UniqueConstraint(
                fields=["company", "plate"],
                name="uniq_vehicle_company_plate",
            )
        ]
        indexes = [
            models.Index(fields=["company", "plate"]),
            models.Index(fields=["company", "status"]),
        ]

    def clean(self):
        if self.assigned_driver_id and self.company_id and self.assigned_driver.company_id != self.company_id:
            raise ValidationError("assigned_driver debe pertenecer a la misma company.")
        if self.assigned_driver_id and not self.assigned_driver.has_driver_role():
            raise ValidationError("assigned_driver debe tener rol de conductor.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        driver_name = self.assigned_driver.name if self.assigned_driver_id and self.assigned_driver.name else "Sin piloto"
        return f"{self.plate} - {driver_name}"
    
