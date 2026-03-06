from django.db import models

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
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
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
        help_text="Patente. Única por empresa.",
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
        help_text="Piloto responsable (si aplica).",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
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

    def __str__(self) -> str:
        return f"{self.company_id} - {self.plate}"
    