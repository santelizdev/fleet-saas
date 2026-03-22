"""Servicios de alertas: generación programada y entrega por email/mensajes internos."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.alerts.models import DocumentAlert, MaintenanceAlert, Notification
from apps.documents.models import DriverLicense, VehicleDocument
from apps.maintenance.models import MaintenanceRecord
from apps.product_analytics.events import track_event

logger = logging.getLogger(__name__)


@dataclass
class AlertGenerationResult:
    """Acumula métricas para los comandos batch sin acoplarlas al CLI."""

    created_alerts: int = 0
    queued_notifications: int = 0


def _maintenance_reminder_days() -> int:
    """Entrega el lead time por fecha con default conservador."""
    return int(getattr(settings, "ALERT_DEFAULT_MAINTENANCE_REMINDER_DAYS", 7))


def _maintenance_reminder_km() -> int:
    """Entrega el lead time por kilometraje para disparar la alerta preventiva."""
    return int(getattr(settings, "ALERT_DEFAULT_MAINTENANCE_REMINDER_KM", 500))


def _alert_generation_batch_size() -> int:
    """Permite procesar datasets grandes sin materializar toda la tabla en memoria."""
    return int(getattr(settings, "ALERT_GENERATION_BATCH_SIZE", 500))


def _assigned_user_for_document(document: VehicleDocument):
    """Usa el conductor asignado como destinatario principal cuando existe."""
    return getattr(document.vehicle, "assigned_driver", None)


def _assigned_user_for_license(license_doc: DriverLicense):
    """La licencia siempre notifica al conductor dueño del documento."""
    return license_doc.driver


def _assigned_user_for_maintenance(record: MaintenanceRecord):
    """Mantenemos compatibilidad con la lógica previa del módulo de alertas."""
    return getattr(record.vehicle, "assigned_driver", None)


def _notification_payload(*, alert_kind: str, message: str, due_date=None, due_km=None, user_id=None) -> dict:
    """Normaliza el payload que comparten mensajes internos, email y futuras exportaciones."""
    payload = {
        "alert_kind": alert_kind,
        "message": message,
    }
    if due_date is not None:
        payload["due_date"] = str(due_date)
    if due_km is not None:
        payload["due_km"] = due_km
    if user_id is not None:
        payload["user_id"] = user_id
    return payload


def build_notification_content(notification: Notification) -> tuple[str, str, dict]:
    """Construye asunto, cuerpo y payload en un solo punto para todos los canales."""
    if notification.document_alert_id:
        alert = notification.document_alert
        if alert.vehicle_document_id:
            context = f"Vehículo {alert.vehicle_document.vehicle.plate} - {alert.vehicle_document.get_type_display()}"
        else:
            context = f"Licencia - {alert.driver_license.driver.email}"
        subject_prefix = "Vencimiento" if alert.kind == DocumentAlert.KIND_EXPIRY else "Documento vencido"
        subject = f"[RutaCore] {subject_prefix}: {context}"
        body = f"{alert.message}\nFecha objetivo: {alert.due_date}\nEstado actual: {alert.get_state_display()}"
        payload = {
            **notification.payload,
            "context": context,
            "entity": "document_alert",
            "alert_id": alert.id,
        }
        return subject, body, payload

    alert = notification.maintenance_alert
    context = f"Vehículo {alert.vehicle.plate}"
    is_overdue = alert.kind in {MaintenanceAlert.KIND_OVERDUE_DATE, MaintenanceAlert.KIND_OVERDUE_KM}
    subject_prefix = "Mantención vencida" if is_overdue else "Mantención próxima"
    deadline = f"Fecha objetivo: {alert.due_date}" if alert.due_date else f"Km objetivo: {alert.due_km}"
    subject = f"[RutaCore] {subject_prefix}: {context}"
    body = f"{alert.message}\n{deadline}\nEstado actual: {alert.get_state_display()}"
    payload = {
        **notification.payload,
        "context": context,
        "entity": "maintenance_alert",
        "alert_id": alert.id,
    }
    return subject, body, payload


def _create_notification(
    *,
    company_id: int,
    document_alert: DocumentAlert | None,
    maintenance_alert: MaintenanceAlert | None,
    channel: str,
    recipient: str,
    payload: dict,
) -> bool:
    """Crea una notificación si no existe ya para ese alert+canal+destino."""
    _, created = Notification.objects.get_or_create(
        company_id=company_id,
        document_alert=document_alert,
        maintenance_alert=maintenance_alert,
        channel=channel,
        recipient=recipient,
        defaults={
            "status": Notification.STATUS_QUEUED,
            "payload": payload,
        },
    )
    return created


def queue_alert_notifications(*, document_alert: DocumentAlert | None = None, maintenance_alert: MaintenanceAlert | None = None) -> int:
    """Fanout conservador: mantenemos `in_app` y añadimos email si hay destinatario útil."""
    alert = document_alert or maintenance_alert
    if alert is None:
        return 0

    user = None
    if document_alert:
        if document_alert.vehicle_document_id:
            user = _assigned_user_for_document(document_alert.vehicle_document)
        elif document_alert.driver_license_id:
            user = _assigned_user_for_license(document_alert.driver_license)
    else:
        record = None
        if maintenance_alert.maintenance_record_id:
            record = maintenance_alert.maintenance_record
        elif maintenance_alert.maintenance_record_ref:
            record = (
                MaintenanceRecord.objects.filter(id=maintenance_alert.maintenance_record_ref)
                .select_related("vehicle", "vehicle__assigned_driver")
                .first()
            )
        if record:
            user = _assigned_user_for_maintenance(record)
        else:
            logger.warning(
                "Maintenance alert %s has no resolvable maintenance record; notifications will stay in-app only.",
                maintenance_alert.id,
            )

    recipient = getattr(user, "email", "") or ""
    payload = _notification_payload(
        alert_kind=alert.kind,
        message=alert.message,
        due_date=getattr(alert, "due_date", None),
        due_km=getattr(alert, "due_km", None),
        user_id=getattr(user, "id", None),
    )

    created_count = 0
    if _create_notification(
        company_id=alert.company_id,
        document_alert=document_alert,
        maintenance_alert=maintenance_alert,
        channel=Notification.CHANNEL_IN_APP,
        recipient=recipient,
        payload=payload,
    ):
        created_count += 1

    if recipient and _create_notification(
        company_id=alert.company_id,
        document_alert=document_alert,
        maintenance_alert=maintenance_alert,
        channel=Notification.CHANNEL_EMAIL,
        recipient=recipient,
        payload=payload,
    ):
        created_count += 1

    return created_count


def _track_queued_notifications(company_id: int, kind: str, created_notifications: int) -> None:
    """Evita emitir analytics si no hubo notificaciones nuevas en cola."""
    if created_notifications <= 0:
        return
    track_event(company_id=company_id, event_name="alert_sent", payload={"kind": kind, "queued_notifications": created_notifications})


def _sync_document_statuses(today: date) -> None:
    """Mantiene los estados documentales alineados con la fecha actual."""
    VehicleDocument.objects.filter(
        is_current=True,
        status=VehicleDocument.STATUS_ACTIVE,
        expiry_date__lt=today,
    ).update(status=VehicleDocument.STATUS_EXPIRED)
    DriverLicense.objects.filter(
        is_current=True,
        status=DriverLicense.STATUS_ACTIVE,
        expiry_date__lt=today,
    ).update(status=DriverLicense.STATUS_EXPIRED)


def _queue_document_alert(alert: DocumentAlert, *, kind_for_tracking: str, result: AlertGenerationResult) -> None:
    queued = queue_alert_notifications(document_alert=alert)
    result.queued_notifications += queued
    _track_queued_notifications(alert.company_id, kind_for_tracking, queued)


def _queue_maintenance_alert(alert: MaintenanceAlert, *, kind_for_tracking: str, result: AlertGenerationResult) -> None:
    queued = queue_alert_notifications(maintenance_alert=alert)
    result.queued_notifications += queued
    _track_queued_notifications(alert.company_id, kind_for_tracking, queued)


def _ensure_maintenance_record_link(alert: MaintenanceAlert, record: MaintenanceRecord) -> None:
    """Completa el FK real sin romper idempotencia sobre alertas históricas."""
    if alert.maintenance_record_id == record.id:
        return
    alert.maintenance_record = record
    alert.maintenance_record_ref = str(record.id)
    alert.save(update_fields=["maintenance_record", "maintenance_record_ref"])


def _ensure_document_alerts_for_document(doc: VehicleDocument, today: date, result: AlertGenerationResult) -> None:
    """Crea recordatorios previos y alertas vencidas sin duplicar la base actual."""
    reminder_date = doc.expiry_date - timedelta(days=doc.reminder_days_before)

    if reminder_date <= today <= doc.expiry_date:
        alert, created = DocumentAlert.objects.get_or_create(
            company_id=doc.company_id,
            vehicle_document=doc,
            driver_license=None,
            kind=DocumentAlert.KIND_EXPIRY,
            scheduled_for=reminder_date,
            defaults={
                "due_date": doc.expiry_date,
                "message": f"Documento {doc.get_type_display()} del vehículo {doc.vehicle.plate} vence el {doc.expiry_date}",
            },
        )
        if created:
            result.created_alerts += 1
        _queue_document_alert(alert, kind_for_tracking="document", result=result)

    if today > doc.expiry_date:
        alert, created = DocumentAlert.objects.get_or_create(
            company_id=doc.company_id,
            vehicle_document=doc,
            driver_license=None,
            kind=DocumentAlert.KIND_EXPIRED,
            scheduled_for=doc.expiry_date,
            defaults={
                "due_date": doc.expiry_date,
                "message": f"Documento {doc.get_type_display()} del vehículo {doc.vehicle.plate} venció el {doc.expiry_date}",
            },
        )
        if created:
            result.created_alerts += 1
        _queue_document_alert(alert, kind_for_tracking="document_overdue", result=result)


def _ensure_document_alerts_for_license(license_doc: DriverLicense, today: date, result: AlertGenerationResult) -> None:
    """Replica la lógica documental para licencias de conducir."""
    reminder_date = license_doc.expiry_date - timedelta(days=license_doc.reminder_days_before)

    if reminder_date <= today <= license_doc.expiry_date:
        alert, created = DocumentAlert.objects.get_or_create(
            company_id=license_doc.company_id,
            vehicle_document=None,
            driver_license=license_doc,
            kind=DocumentAlert.KIND_EXPIRY,
            scheduled_for=reminder_date,
            defaults={
                "due_date": license_doc.expiry_date,
                "message": f"Licencia de {license_doc.driver.email} vence el {license_doc.expiry_date}",
            },
        )
        if created:
            result.created_alerts += 1
        _queue_document_alert(alert, kind_for_tracking="license", result=result)

    if today > license_doc.expiry_date:
        alert, created = DocumentAlert.objects.get_or_create(
            company_id=license_doc.company_id,
            vehicle_document=None,
            driver_license=license_doc,
            kind=DocumentAlert.KIND_EXPIRED,
            scheduled_for=license_doc.expiry_date,
            defaults={
                "due_date": license_doc.expiry_date,
                "message": f"Licencia de {license_doc.driver.email} venció el {license_doc.expiry_date}",
            },
        )
        if created:
            result.created_alerts += 1
        _queue_document_alert(alert, kind_for_tracking="license_overdue", result=result)


def _ensure_maintenance_alerts(record: MaintenanceRecord, today: date, result: AlertGenerationResult) -> None:
    """Genera alertas previas y vencidas por fecha y kilometraje."""
    if record.next_due_date:
        reminder_date = record.next_due_date - timedelta(days=_maintenance_reminder_days())
        if reminder_date <= today <= record.next_due_date:
            alert, created = MaintenanceAlert.objects.get_or_create(
                company_id=record.company_id,
                vehicle_id=record.vehicle_id,
                maintenance_record_ref=str(record.id),
                kind=MaintenanceAlert.KIND_BY_DATE,
                due_date=record.next_due_date,
                defaults={
                    "message": f"Mantención por fecha para {record.vehicle.plate} programada el {record.next_due_date}",
                },
            )
            _ensure_maintenance_record_link(alert, record)
            if created:
                result.created_alerts += 1
            _queue_maintenance_alert(alert, kind_for_tracking="maintenance_date", result=result)

        if today > record.next_due_date:
            alert, created = MaintenanceAlert.objects.get_or_create(
                company_id=record.company_id,
                vehicle_id=record.vehicle_id,
                maintenance_record_ref=str(record.id),
                kind=MaintenanceAlert.KIND_OVERDUE_DATE,
                due_date=record.next_due_date,
                defaults={
                    "message": f"Mantención vencida por fecha para {record.vehicle.plate} desde el {record.next_due_date}",
                },
            )
            _ensure_maintenance_record_link(alert, record)
            if created:
                result.created_alerts += 1
            _queue_maintenance_alert(alert, kind_for_tracking="maintenance_date_overdue", result=result)

    if record.next_due_km is not None:
        reminder_km = max(0, record.next_due_km - _maintenance_reminder_km())
        if reminder_km <= record.vehicle.current_km < record.next_due_km:
            alert, created = MaintenanceAlert.objects.get_or_create(
                company_id=record.company_id,
                vehicle_id=record.vehicle_id,
                maintenance_record_ref=str(record.id),
                kind=MaintenanceAlert.KIND_BY_KM,
                due_km=record.next_due_km,
                defaults={
                    "message": f"Mantención por km para {record.vehicle.plate} cerca de {record.next_due_km} km",
                },
            )
            _ensure_maintenance_record_link(alert, record)
            if created:
                result.created_alerts += 1
            _queue_maintenance_alert(alert, kind_for_tracking="maintenance_km", result=result)

        if record.vehicle.current_km >= record.next_due_km:
            alert, created = MaintenanceAlert.objects.get_or_create(
                company_id=record.company_id,
                vehicle_id=record.vehicle_id,
                maintenance_record_ref=str(record.id),
                kind=MaintenanceAlert.KIND_OVERDUE_KM,
                due_km=record.next_due_km,
                defaults={
                    "message": f"Mantención vencida por km para {record.vehicle.plate}; umbral {record.next_due_km} km",
                },
            )
            _ensure_maintenance_record_link(alert, record)
            if created:
                result.created_alerts += 1
            _queue_maintenance_alert(alert, kind_for_tracking="maintenance_km_overdue", result=result)


@transaction.atomic
def generate_scheduled_alerts(*, today: date | None = None) -> AlertGenerationResult:
    """Punto único de generación diaria para documentos, licencias y mantenimientos."""
    today = today or timezone.localdate()
    result = AlertGenerationResult()
    batch_size = _alert_generation_batch_size()
    _sync_document_statuses(today)

    docs = VehicleDocument.objects.filter(
        is_current=True,
        status__in=[VehicleDocument.STATUS_ACTIVE, VehicleDocument.STATUS_EXPIRED],
    ).select_related("vehicle", "vehicle__assigned_driver").order_by("id")
    for doc in docs.iterator(chunk_size=batch_size):
        _ensure_document_alerts_for_document(doc, today, result)

    licenses = DriverLicense.objects.filter(
        is_current=True,
        status__in=[DriverLicense.STATUS_ACTIVE, DriverLicense.STATUS_EXPIRED],
    ).select_related("driver").order_by("id")
    for license_doc in licenses.iterator(chunk_size=batch_size):
        _ensure_document_alerts_for_license(license_doc, today, result)

    maintenance_records = MaintenanceRecord.objects.filter(
        status=MaintenanceRecord.STATUS_OPEN,
    ).select_related("vehicle", "vehicle__assigned_driver").order_by("id")
    for record in maintenance_records.iterator(chunk_size=batch_size):
        _ensure_maintenance_alerts(record, today, result)

    return result


def send_notification(notification: Notification) -> None:
    """Despacha por canal y reutiliza el contenido ya centralizado."""
    if notification.channel == Notification.CHANNEL_IN_APP:
        return

    if notification.channel == Notification.CHANNEL_EMAIL:
        if not notification.recipient:
            raise ValueError("Recipient vacío para notificación email.")
        subject, body, _ = build_notification_content(notification)
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@fleet.local"),
            recipient_list=[notification.recipient],
            fail_silently=False,
        )
        return

    raise ValueError(f"Canal de notificación no soportado: {notification.channel}")
