from django.db import models
from django.conf import settings

from apps.companies.models import Company


class AuditLog(models.Model):
    """
    Log de auditoría. Debe ser append-only (solo INSERT).

    Nota importante:
    - Este modelo NO debe importar User directamente para evitar imports circulares.
      Se usa settings.AUTH_USER_MODEL en el ForeignKey.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        help_text="Puede ser null si la acción es global (superadmin).",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_actions",
    )
    action = models.CharField(
        max_length=64,
        help_text="Ej: vehicle.create, expense.approve, document.renew, etc.",
    )
    object_type = models.CharField(
        max_length=64,
        help_text="Ej: Vehicle, VehicleDocument, User, etc.",
    )
    object_id = models.CharField(
        max_length=64,
        help_text="ID del objeto afectado (string para soportar int/uuid).",
    )
    before_json = models.JSONField(null=True, blank=True)
    after_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "created_at"]),
            models.Index(fields=["object_type", "object_id"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self) -> str:
        return f"{self.created_at} {self.action} {self.object_type}:{self.object_id}"