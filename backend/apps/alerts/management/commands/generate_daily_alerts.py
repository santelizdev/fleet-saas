from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.alerts.models import DocumentAlert, JobRun, MaintenanceAlert, Notification
from apps.documents.models import DriverLicense, VehicleDocument
from apps.maintenance.models import MaintenanceRecord
from apps.product_analytics.events import track_event


class Command(BaseCommand):
    help = "Genera alertas de documentos/licencias que vencen y encola notificaciones."

    def handle(self, *args, **options):
        started_at = timezone.now()
        status = JobRun.STATUS_SUCCESS
        today = timezone.localdate()
        created_alerts = 0
        queued_notifications = 0
        try:
            docs = VehicleDocument.objects.filter(
                is_current=True,
                status=VehicleDocument.STATUS_ACTIVE,
            )
            for doc in docs:
                scheduled_for = doc.expiry_date - timedelta(days=doc.reminder_days_before)
                if scheduled_for != today:
                    continue

                alert, created = DocumentAlert.objects.get_or_create(
                    company_id=doc.company_id,
                    vehicle_document=doc,
                    driver_license=None,
                    kind=DocumentAlert.KIND_EXPIRY,
                    scheduled_for=scheduled_for,
                    defaults={
                        "due_date": doc.expiry_date,
                        "message": f"Documento {doc.type} vence el {doc.expiry_date}",
                    },
                )
                if created:
                    created_alerts += 1

                notification, n_created = Notification.objects.get_or_create(
                    company_id=doc.company_id,
                    document_alert=alert,
                    maintenance_alert=None,
                    channel=Notification.CHANNEL_IN_APP,
                    recipient=doc.vehicle.assigned_driver.email if doc.vehicle.assigned_driver else "",
                    defaults={"status": Notification.STATUS_QUEUED},
                )
                if n_created and notification.status == Notification.STATUS_QUEUED:
                    queued_notifications += 1
                    track_event(company_id=doc.company_id, event_name="alert_sent", payload={"kind": "document"})

            licenses = DriverLicense.objects.filter(
                is_current=True,
                status=DriverLicense.STATUS_ACTIVE,
            )
            for license_doc in licenses:
                scheduled_for = license_doc.expiry_date - timedelta(days=license_doc.reminder_days_before)
                if scheduled_for != today:
                    continue

                alert, created = DocumentAlert.objects.get_or_create(
                    company_id=license_doc.company_id,
                    vehicle_document=None,
                    driver_license=license_doc,
                    kind=DocumentAlert.KIND_EXPIRY,
                    scheduled_for=scheduled_for,
                    defaults={
                        "due_date": license_doc.expiry_date,
                        "message": f"Licencia de {license_doc.driver.email} vence el {license_doc.expiry_date}",
                    },
                )
                if created:
                    created_alerts += 1

                notification, n_created = Notification.objects.get_or_create(
                    company_id=license_doc.company_id,
                    document_alert=alert,
                    maintenance_alert=None,
                    channel=Notification.CHANNEL_IN_APP,
                    recipient=license_doc.driver.email,
                    defaults={"status": Notification.STATUS_QUEUED},
                )
                if n_created and notification.status == Notification.STATUS_QUEUED:
                    queued_notifications += 1
                    track_event(company_id=license_doc.company_id, event_name="alert_sent", payload={"kind": "license"})

            maintenance_records = MaintenanceRecord.objects.filter(
                status=MaintenanceRecord.STATUS_OPEN,
            ).select_related("vehicle")
            for record in maintenance_records:
                if record.next_due_date == today:
                    alert, created = MaintenanceAlert.objects.get_or_create(
                        company_id=record.company_id,
                        vehicle_id=record.vehicle_id,
                        maintenance_record_ref=str(record.id),
                        kind=MaintenanceAlert.KIND_BY_DATE,
                        due_date=record.next_due_date,
                        defaults={
                            "message": f"Mantencion por fecha para {record.vehicle.plate}",
                        },
                    )
                    if created:
                        created_alerts += 1
                    _, n_created = Notification.objects.get_or_create(
                        company_id=record.company_id,
                        document_alert=None,
                        maintenance_alert=alert,
                        channel=Notification.CHANNEL_IN_APP,
                        recipient=record.vehicle.assigned_driver.email if record.vehicle.assigned_driver else "",
                        defaults={"status": Notification.STATUS_QUEUED},
                    )
                    if n_created:
                        queued_notifications += 1
                        track_event(company_id=record.company_id, event_name="alert_sent", payload={"kind": "maintenance_date"})

                if record.next_due_km is not None and record.vehicle.current_km >= record.next_due_km:
                    alert, created = MaintenanceAlert.objects.get_or_create(
                        company_id=record.company_id,
                        vehicle_id=record.vehicle_id,
                        maintenance_record_ref=str(record.id),
                        kind=MaintenanceAlert.KIND_BY_KM,
                        due_km=record.next_due_km,
                        defaults={
                            "message": f"Mantencion por km para {record.vehicle.plate}",
                        },
                    )
                    if created:
                        created_alerts += 1
                    _, n_created = Notification.objects.get_or_create(
                        company_id=record.company_id,
                        document_alert=None,
                        maintenance_alert=alert,
                        channel=Notification.CHANNEL_IN_APP,
                        recipient=record.vehicle.assigned_driver.email if record.vehicle.assigned_driver else "",
                        defaults={"status": Notification.STATUS_QUEUED},
                    )
                    if n_created:
                        queued_notifications += 1
                        track_event(company_id=record.company_id, event_name="alert_sent", payload={"kind": "maintenance_km"})
        except Exception:
            status = JobRun.STATUS_FAILED
            raise
        finally:
            JobRun.objects.create(
                job_name="generate_daily_alerts",
                status=status,
                details={
                    "created_alerts": created_alerts,
                    "queued_notifications": queued_notifications,
                },
                started_at=started_at,
                finished_at=timezone.now(),
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Alertas creadas: {created_alerts}. Notificaciones encoladas: {queued_notifications}."
            )
        )
