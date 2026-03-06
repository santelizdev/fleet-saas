from django.conf import settings
from django.db import models

from apps.companies.models import Company


class ReportExportLog(models.Model):
    FORMAT_CSV = "csv"
    FORMAT_XLSX = "xlsx"
    FORMAT_CHOICES = [
        (FORMAT_CSV, "CSV"),
        (FORMAT_XLSX, "XLSX"),
    ]

    STATUS_COMPLETED = "completed"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_COMPLETED, "Completed"),
        (STATUS_REJECTED, "Rejected"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="report_export_logs")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="report_export_logs",
    )
    report_type = models.CharField(max_length=64)
    export_format = models.CharField(max_length=8, choices=FORMAT_CHOICES, default=FORMAT_CSV)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_COMPLETED)
    row_count = models.PositiveIntegerField(default=0)
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "created_at"]),
            models.Index(fields=["company", "report_type", "created_at"]),
        ]
