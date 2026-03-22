from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import models, transaction

from apps.accounts.models import User
from apps.companies.models import Company
from apps.vehicles.models import Vehicle


class Attachment(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="attachments")
    storage_key = models.CharField(max_length=512, unique=True)
    original_name = models.CharField(max_length=255, blank=True, default="")
    size_bytes = models.PositiveBigIntegerField()
    mime_type = models.CharField(max_length=128)
    sha256 = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "created_at"]),
            models.Index(fields=["company", "mime_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.company_id}:{self.storage_key}"

    @property
    def file_url(self) -> str:
        if not self.storage_key:
            return ""
        return default_storage.url(self.storage_key)


class VehicleDocument(models.Model):
    TYPE_PERMISO_CIRCULACION = "permiso_circulacion"
    TYPE_REVISION_TECNICA = "revision_tecnica"
    TYPE_TECNOMECANICA = "tecnomecanica"
    TYPE_SEGURO = "seguro"
    TYPE_SOAP = TYPE_SEGURO
    TYPE_GASES = "gases"
    TYPE_OTRO = "otro"

    TYPE_CHOICES = [
        (TYPE_PERMISO_CIRCULACION, "Permiso de circulacion"),
        (TYPE_REVISION_TECNICA, "Revision tecnica"),
        (TYPE_TECNOMECANICA, "Tecnomecanica"),
        (TYPE_SEGURO, "SOAP"),
        (TYPE_GASES, "Gases"),
        (TYPE_OTRO, "Otro"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_REPLACED = "replaced"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_REPLACED, "Replaced"),
        (STATUS_EXPIRED, "Expired"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="vehicle_documents")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="documents")
    type = models.CharField(max_length=64, choices=TYPE_CHOICES)
    issue_date = models.DateField()
    expiry_date = models.DateField()
    reminder_days_before = models.PositiveIntegerField(default=30)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    notes = models.TextField(blank=True, default="")
    previous_version = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="next_versions",
    )
    is_current = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_vehicle_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "vehicle", "type"]),
            models.Index(fields=["company", "expiry_date"]),
            models.Index(fields=["company", "is_current"]),
        ]

    def clean(self):
        if self.issue_date and self.expiry_date and self.expiry_date <= self.issue_date:
            raise ValidationError("expiry_date debe ser mayor que issue_date.")

        if self.vehicle_id and self.company_id and self.vehicle.company_id != self.company_id:
            raise ValidationError("Vehicle y Document deben pertenecer a la misma company.")

        if self.created_by_id and self.company_id and self.created_by.company_id != self.company_id:
            raise ValidationError("created_by debe pertenecer a la misma company.")
        if self.previous_version_id:
            prev = self.previous_version
            if prev.company_id != self.company_id:
                raise ValidationError("previous_version debe ser de la misma company.")
            if prev.vehicle_id != self.vehicle_id:
                raise ValidationError("previous_version debe ser del mismo vehicle.")
            if prev.type != self.type:
                raise ValidationError("previous_version debe ser del mismo tipo de documento.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @transaction.atomic
    def renew(self, *, issue_date, expiry_date, notes="", created_by: User | None = None) -> "VehicleDocument":
        if not self.is_current:
            raise ValidationError("Solo se puede renovar un documento actual.")

        self.is_current = False
        self.status = self.STATUS_REPLACED
        self.save(update_fields=["is_current", "status"])

        return VehicleDocument.objects.create(
            company_id=self.company_id,
            vehicle_id=self.vehicle_id,
            type=self.type,
            issue_date=issue_date,
            expiry_date=expiry_date,
            reminder_days_before=self.reminder_days_before,
            status=self.STATUS_ACTIVE,
            notes=notes,
            previous_version=self,
            is_current=True,
            created_by=created_by,
        )

    def __str__(self) -> str:
        driver_name = self.vehicle.assigned_driver.name if self.vehicle.assigned_driver_id and self.vehicle.assigned_driver.name else "Sin piloto"
        return f"{self.vehicle.plate} - {self.get_type_display()} - {driver_name}"

    @property
    def support_attachment(self) -> Attachment | None:
        link = self.attachment_links.select_related("attachment").order_by("-id").first()
        return link.attachment if link else None


class VehicleDocumentAttachment(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="vehicle_document_attachments")
    vehicle_document = models.ForeignKey(
        VehicleDocument,
        on_delete=models.CASCADE,
        related_name="attachment_links",
    )
    attachment = models.ForeignKey(Attachment, on_delete=models.CASCADE, related_name="vehicle_document_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["vehicle_document", "attachment"],
                name="uniq_vehicle_document_attachment",
            )
        ]
        indexes = [
            models.Index(fields=["company", "vehicle_document"]),
        ]

    def clean(self):
        if self.company_id and self.vehicle_document_id and self.vehicle_document.company_id != self.company_id:
            raise ValidationError("vehicle_document debe pertenecer a la misma company.")
        if self.company_id and self.attachment_id and self.attachment.company_id != self.company_id:
            raise ValidationError("attachment debe pertenecer a la misma company.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class DriverLicense(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_REPLACED = "replaced"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_REPLACED, "Replaced"),
        (STATUS_EXPIRED, "Expired"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="driver_licenses")
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="driver_licenses")
    license_number = models.CharField(max_length=64)
    category = models.CharField(max_length=64, blank=True, default="")
    issue_date = models.DateField()
    expiry_date = models.DateField()
    reminder_days_before = models.PositiveIntegerField(default=30)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    previous_version = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="next_versions",
    )
    is_current = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_driver_licenses",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "driver", "license_number", "is_current"],
                name="uniq_driver_license_current",
            )
        ]
        indexes = [
            models.Index(fields=["company", "expiry_date"]),
            models.Index(fields=["company", "is_current"]),
        ]

    def clean(self):
        if self.issue_date and self.expiry_date and self.expiry_date <= self.issue_date:
            raise ValidationError("expiry_date debe ser mayor que issue_date.")
        if self.driver_id and self.company_id and self.driver.company_id != self.company_id:
            raise ValidationError("Driver y DriverLicense deben pertenecer a la misma company.")
        if self.driver_id and not self.driver.has_driver_role():
            raise ValidationError("driver debe tener rol de conductor.")
        if self.created_by_id and self.company_id and self.created_by.company_id != self.company_id:
            raise ValidationError("created_by debe pertenecer a la misma company.")

        if self.previous_version_id:
            prev = self.previous_version
            if prev.company_id != self.company_id:
                raise ValidationError("previous_version debe ser de la misma company.")
            if prev.driver_id != self.driver_id:
                raise ValidationError("previous_version debe ser del mismo driver.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @transaction.atomic
    def renew(self, *, issue_date, expiry_date, created_by: User | None = None) -> "DriverLicense":
        if not self.is_current:
            raise ValidationError("Solo se puede renovar una licencia actual.")

        self.is_current = False
        self.status = self.STATUS_REPLACED
        self.save(update_fields=["is_current", "status"])

        return DriverLicense.objects.create(
            company_id=self.company_id,
            driver_id=self.driver_id,
            license_number=self.license_number,
            category=self.category,
            issue_date=issue_date,
            expiry_date=expiry_date,
            reminder_days_before=self.reminder_days_before,
            status=self.STATUS_ACTIVE,
            previous_version=self,
            is_current=True,
            created_by=created_by,
        )


    def __str__(self) -> str:
        return f"{self.driver.name} - {self.license_number}"

    @property
    def support_attachment(self) -> Attachment | None:
        link = self.attachment_links.select_related("attachment").order_by("-id").first()
        return link.attachment if link else None


class DriverLicenseAttachment(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="driver_license_attachments")
    driver_license = models.ForeignKey(
        DriverLicense,
        on_delete=models.CASCADE,
        related_name="attachment_links",
    )
    attachment = models.ForeignKey(Attachment, on_delete=models.CASCADE, related_name="driver_license_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["driver_license", "attachment"],
                name="uniq_driver_license_attachment",
            )
        ]
        indexes = [
            models.Index(fields=["company", "driver_license"]),
        ]

    def clean(self):
        if self.company_id and self.driver_license_id and self.driver_license.company_id != self.company_id:
            raise ValidationError("driver_license debe pertenecer a la misma company.")
        if self.company_id and self.attachment_id and self.attachment.company_id != self.company_id:
            raise ValidationError("attachment debe pertenecer a la misma company.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
