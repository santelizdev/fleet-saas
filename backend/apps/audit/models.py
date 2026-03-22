from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apps.companies.models import Company


class AuditLog(models.Model):
    """
    Log de auditoría. Debe ser append-only (solo INSERT).

    Nota importante:
    - Este modelo NO debe importar User directamente para evitar imports circulares.
      Se usa settings.AUTH_USER_MODEL en el ForeignKey.
    """

    SOURCE_ADMIN = "admin"
    SOURCE_API = "api"
    SOURCE_AUTH = "auth"
    SOURCE_SYSTEM = "system"
    SOURCE_NOTIFICATION = "notification"
    SOURCE_CHOICES = [
        (SOURCE_ADMIN, _("Admin")),
        (SOURCE_API, _("API")),
        (SOURCE_AUTH, _("Autenticación")),
        (SOURCE_SYSTEM, _("Sistema")),
        (SOURCE_NOTIFICATION, _("Notificaciones")),
    ]

    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_INFO = "info"
    STATUS_WARNING = "warning"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, _("Correcto")),
        (STATUS_FAILED, _("Fallido")),
        (STATUS_INFO, _("Informativo")),
        (STATUS_WARNING, _("Advertencia")),
    ]

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
    source = models.CharField(max_length=24, choices=SOURCE_CHOICES, default=SOURCE_SYSTEM)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_INFO)
    action = models.CharField(
        max_length=64,
        help_text="Ej: vehicle.create, expense.approve, document.renew, etc.",
    )
    summary = models.CharField(max_length=255, blank=True, default="")
    object_type = models.CharField(
        max_length=64,
        help_text="Ej: Vehicle, VehicleDocument, User, etc.",
    )
    object_id = models.CharField(
        max_length=64,
        help_text="ID del objeto afectado (string para soportar int/uuid).",
    )
    metadata_json = models.JSONField(null=True, blank=True)
    before_json = models.JSONField(null=True, blank=True)
    after_json = models.JSONField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True, default="")
    remote_addr = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "created_at"]),
            models.Index(fields=["object_type", "object_id"]),
            models.Index(fields=["action"]),
            models.Index(fields=["source", "status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.created_at} {self.action} {self.object_type}:{self.object_id}"
