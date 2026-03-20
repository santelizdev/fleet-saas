from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.alerts.models import JobRun
from apps.alerts.services import generate_scheduled_alerts


class Command(BaseCommand):
    help = "Genera alertas de documentos/licencias que vencen y encola notificaciones."

    def handle(self, *args, **options):
        started_at = timezone.now()
        status = JobRun.STATUS_SUCCESS
        result = None
        try:
            result = generate_scheduled_alerts(today=timezone.localdate())
        except Exception:
            status = JobRun.STATUS_FAILED
            raise
        finally:
            JobRun.objects.create(
                job_name="generate_daily_alerts",
                status=status,
                details={
                    "created_alerts": getattr(result, "created_alerts", 0),
                    "queued_notifications": getattr(result, "queued_notifications", 0),
                },
                started_at=started_at,
                finished_at=timezone.now(),
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Alertas creadas: {result.created_alerts}. Notificaciones encoladas: {result.queued_notifications}."
            )
        )
