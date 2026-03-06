from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.alerts.models import AlertState, DocumentAlert, JobRun, Notification


class Command(BaseCommand):
    help = "Procesa cola de notificaciones (queued/failed) con retry + backoff."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--max-attempts", type=int, default=5)

    def _send_notification(self, notification: Notification):
        if notification.channel == Notification.CHANNEL_IN_APP:
            return

        # Placeholder para envío real. Forzamos validación mínima de recipient.
        if not notification.recipient:
            raise ValueError("Recipient vacío para notificación email.")

    def handle(self, *args, **options):
        started_at = timezone.now()
        job_status = JobRun.STATUS_SUCCESS
        now = timezone.now()
        limit = options["limit"]
        max_attempts = options["max_attempts"]
        sent = 0
        failed = 0
        skipped_dlq = 0

        try:
            notifications = Notification.objects.filter(
                status__in=[Notification.STATUS_QUEUED, Notification.STATUS_FAILED],
                available_at__lte=now,
            ).order_by("created_at")[:limit]

            for notification in notifications:
                if notification.attempts >= max_attempts:
                    skipped_dlq += 1
                    continue

                try:
                    self._send_notification(notification)
                    notification.mark_sent()
                    sent += 1
                    if notification.document_alert_id:
                        DocumentAlert.objects.filter(id=notification.document_alert_id).update(state=AlertState.SENT)
                except Exception as exc:
                    notification.mark_failed(exc)
                    failed += 1
        except Exception:
            job_status = JobRun.STATUS_FAILED
            raise
        finally:
            JobRun.objects.create(
                job_name="process_notifications",
                status=job_status,
                details={"sent": sent, "failed": failed, "dlq": skipped_dlq},
                started_at=started_at,
                finished_at=timezone.now(),
            )

        self.stdout.write(
            self.style.SUCCESS(f"Procesadas: sent={sent}, failed={failed}, dlq={skipped_dlq}.")
        )
