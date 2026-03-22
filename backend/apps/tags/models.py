"""Modelos base para analítica operacional y financiera de TAG / pórticos."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.companies.models import Company
from apps.vehicles.models import Vehicle


class TollRoad(models.Model):
    """Autopista o concesionaria a la que pertenecen los pórticos."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="toll_roads")
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=32, blank=True, default="")
    operator_name = models.CharField(max_length=120, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Autopista"
        verbose_name_plural = "Autopistas"
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="uniq_toll_road_company_name"),
        ]
        indexes = [models.Index(fields=["company", "name"])]

    def __str__(self) -> str:
        return self.name


class TollGate(models.Model):
    """Pórtico físico o lógico usado para los tránsitos TAG."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="toll_gates")
    road = models.ForeignKey(TollRoad, on_delete=models.CASCADE, related_name="gates")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=120)
    direction = models.CharField(max_length=64, blank=True, default="")
    km_marker = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pórtico"
        verbose_name_plural = "Pórticos"
        constraints = [
            models.UniqueConstraint(fields=["company", "road", "code"], name="uniq_toll_gate_company_road_code"),
        ]
        indexes = [
            models.Index(fields=["company", "road"]),
            models.Index(fields=["company", "code"]),
        ]

    def clean(self):
        if self.company_id and self.road_id and self.road.company_id != self.company_id:
            raise ValidationError("road debe pertenecer a la misma company.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.road.name} / {self.name}"


class TagImportBatch(models.Model):
    """Documento fuente o lote de importación desde el proveedor TAG."""

    STATUS_PENDING = "pending"
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendiente"),
        (STATUS_PROCESSED, "Procesado"),
        (STATUS_FAILED, "Con errores"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="tag_import_batches")
    source_name = models.CharField(max_length=120)
    source_file_name = models.CharField(max_length=255, blank=True, default="")
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    total_rows = models.PositiveIntegerField(default=0)
    imported_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tag_import_batches",
    )

    class Meta:
        verbose_name = "Importación TAG"
        verbose_name_plural = "Importaciones TAG"
        indexes = [models.Index(fields=["company", "imported_at"])]

    def clean(self):
        if self.created_by_id and self.company_id and self.created_by.company_id != self.company_id:
            raise ValidationError("created_by debe pertenecer a la misma company.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.source_name} ({self.imported_at:%Y-%m-%d})"


class TagTransit(models.Model):
    """Paso por pórtico detectado desde archivo o integración externa."""

    MATCH_PENDING = "pending"
    MATCH_MATCHED = "matched"
    MATCH_UNMATCHED = "unmatched"
    MATCH_OBSERVED = "observed"
    MATCH_CHOICES = [
        (MATCH_PENDING, "Pendiente"),
        (MATCH_MATCHED, "Conciliado"),
        (MATCH_UNMATCHED, "Sin vehículo"),
        (MATCH_OBSERVED, "Observado"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="tag_transits")
    batch = models.ForeignKey(TagImportBatch, null=True, blank=True, on_delete=models.SET_NULL, related_name="transits")
    road = models.ForeignKey(TollRoad, on_delete=models.CASCADE, related_name="transits")
    gate = models.ForeignKey(TollGate, null=True, blank=True, on_delete=models.SET_NULL, related_name="transits")
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.SET_NULL, related_name="tag_transits")
    detected_plate = models.CharField(max_length=16, blank=True, default="")
    tag_reference = models.CharField(max_length=64, blank=True, default="")
    schedule_code = models.CharField(max_length=32, blank=True, default="")
    invoice_reference = models.CharField(max_length=128, blank=True, default="")
    transit_at = models.DateTimeField()
    transit_date = models.DateField()
    is_weekend = models.BooleanField(default=False)
    amount_clp = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=8, default="CLP")
    match_status = models.CharField(max_length=16, choices=MATCH_CHOICES, default=MATCH_PENDING)
    notes = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tránsito TAG"
        verbose_name_plural = "Tránsitos TAG"
        indexes = [
            models.Index(fields=["company", "transit_date"]),
            models.Index(fields=["company", "vehicle", "transit_date"]),
            models.Index(fields=["company", "detected_plate"]),
            models.Index(fields=["company", "is_weekend", "transit_date"]),
        ]

    def clean(self):
        if self.road_id and self.company_id and self.road.company_id != self.company_id:
            raise ValidationError("road debe pertenecer a la misma company.")
        if self.gate_id and self.company_id and self.gate.company_id != self.company_id:
            raise ValidationError("gate debe pertenecer a la misma company.")
        if self.vehicle_id and self.company_id and self.vehicle.company_id != self.company_id:
            raise ValidationError("vehicle debe pertenecer a la misma company.")
        if self.batch_id and self.company_id and self.batch.company_id != self.company_id:
            raise ValidationError("batch debe pertenecer a la misma company.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        plate = self.vehicle.plate if self.vehicle_id else self.detected_plate or "sin patente"
        return f"{plate} @ {self.transit_at:%Y-%m-%d %H:%M}"


class TagCharge(models.Model):
    """Cobro financiero asociado a un tránsito o consolidado del proveedor TAG."""

    STATUS_PENDING = "pending"
    STATUS_RECONCILED = "reconciled"
    STATUS_UNMATCHED = "unmatched"
    STATUS_DISPUTED = "disputed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendiente"),
        (STATUS_RECONCILED, "Conciliado"),
        (STATUS_UNMATCHED, "Sin vehículo"),
        (STATUS_DISPUTED, "Observado"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="tag_charges")
    transit = models.ForeignKey(TagTransit, null=True, blank=True, on_delete=models.SET_NULL, related_name="charges")
    batch = models.ForeignKey(TagImportBatch, null=True, blank=True, on_delete=models.SET_NULL, related_name="charges")
    road = models.ForeignKey(TollRoad, on_delete=models.CASCADE, related_name="charges")
    gate = models.ForeignKey(TollGate, null=True, blank=True, on_delete=models.SET_NULL, related_name="charges")
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.SET_NULL, related_name="tag_charges")
    detected_plate = models.CharField(max_length=16, blank=True, default="")
    tag_reference = models.CharField(max_length=64, blank=True, default="")
    schedule_code = models.CharField(max_length=32, blank=True, default="")
    invoice_reference = models.CharField(max_length=128, blank=True, default="")
    charge_date = models.DateField()
    billed_at = models.DateTimeField(null=True, blank=True)
    is_weekend = models.BooleanField(default=False)
    amount_clp = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    notes = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cobro TAG"
        verbose_name_plural = "Cobros TAG"
        indexes = [
            models.Index(fields=["company", "charge_date"]),
            models.Index(fields=["company", "vehicle", "charge_date"]),
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "is_weekend", "charge_date"]),
        ]

    def clean(self):
        for relation_name in ("transit", "batch", "road", "gate", "vehicle"):
            related = getattr(self, relation_name, None)
            if related is not None and self.company_id and getattr(related, "company_id", None) != self.company_id:
                raise ValidationError(f"{relation_name} debe pertenecer a la misma company.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        plate = self.vehicle.plate if self.vehicle_id else self.detected_plate or "sin patente"
        return f"{plate} / {self.amount_clp} CLP"
