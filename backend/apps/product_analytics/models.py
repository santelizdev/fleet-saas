from django.conf import settings
from django.db import models

from apps.companies.models import Company


class ProductEvent(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="product_events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="product_events",
    )
    event_name = models.CharField(max_length=64)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "event_name", "created_at"]),
            models.Index(fields=["event_name", "created_at"]),
        ]

    def __str__(self):
        return f"{self.company_id}:{self.event_name}"
