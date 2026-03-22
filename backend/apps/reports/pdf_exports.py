"""Generación PDF del centro de reportes reutilizando el contexto operacional existente."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .services import build_reports_admin_context


def _money(value) -> str:
    amount = int(value or 0)
    return f"${amount:,}".replace(",", ".")


def _table(rows, col_widths=None):
    """Aplica un estilo consistente para que el PDF sea legible sin depender de HTML."""
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#20324D")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("LEADING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def build_operational_report_pdf(filters) -> tuple[bytes, int]:
    """Construye un PDF resumen del centro de reportes y devuelve bytes + fila estimada."""
    context = build_reports_admin_context(filters)
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    section_style = styles["Heading2"]
    body_style = ParagraphStyle("FleetBody", parent=styles["BodyText"], fontSize=9, leading=12)

    story = [
        Paragraph("RutaCore - Reporte operacional", title_style),
        Paragraph(
            f"Periodo: {context['report_filters'].date_from} a {context['report_filters'].date_to}",
            body_style,
        ),
        Spacer(1, 5 * mm),
    ]

    kpis = context["report_kpis"]
    story.extend(
        [
            Paragraph("KPIs principales", section_style),
            _table(
                [
                    ["Vehículos", "Docs por vencer", "Docs vencidos", "Mantenciones abiertas", "Gasto", "Alertas activas", "TAG"],
                    [
                        kpis["vehicles"],
                        kpis["expiring_documents"],
                        kpis["expired_documents"],
                        kpis["open_maintenance"],
                        _money(kpis["expenses_total"]),
                        kpis["active_alerts"],
                        _money(kpis["tag_total"]),
                    ],
                ]
            ),
            Spacer(1, 5 * mm),
        ]
    )

    sections = [
        (
            "Documentos próximos a vencer",
            [["Vehículo", "Tipo", "Vence"]]
            + [
                [item.vehicle.plate, item.get_type_display(), str(item.expiry_date)]
                for item in context["report_expiring_documents"]
            ],
        ),
        (
            "Mantenciones vencidas o próximas",
            [["Vehículo", "Servicio", "Próxima fecha", "Próximo km"]]
            + [
                [
                    item.vehicle.plate,
                    item.description or item.get_type_display(),
                    str(item.next_due_date or "-"),
                    item.next_due_km or "-",
                ]
                for item in context["report_maintenance_upcoming"]
            ]
            + [
                [
                    item.vehicle.plate,
                    item.description or item.get_type_display(),
                    str(item.next_due_date or "-"),
                    item.next_due_km or "-",
                ]
                for item in context["report_maintenance_overdue"]
            ],
        ),
        (
            "Gastos por categoría",
            [["Categoría", "Items", "Total"]]
            + [
                [item["category__name"] or "Sin categoría", item["total_items"], _money(item["total_amount"])]
                for item in context["report_expense_by_category"]
            ],
        ),
        (
            "Resumen de alertas",
            [
                ["Métrica", "Valor"],
                ["Documentos pendientes", context["report_alert_summary"]["documents_pending"]],
                ["Documentos enviados", context["report_alert_summary"]["documents_sent"]],
                ["Mantenciones pendientes", context["report_alert_summary"]["maintenance_pending"]],
                ["Mantenciones enviadas", context["report_alert_summary"]["maintenance_sent"]],
            ],
        ),
        (
            "TAG / Pórticos",
            [["Métrica", "Valor"]]
            + [
                ["Monto del período", _money(context["report_tag_summary"]["total_amount"])],
                ["Pendientes", context["report_tag_summary"]["pending_count"]],
                ["Sin match", context["report_tag_summary"]["unmatched_count"]],
            ],
        ),
    ]

    row_count = 1
    for title, rows in sections:
        normalized_rows = rows if len(rows) > 1 else rows + [["Sin datos para el filtro actual"]]
        story.append(Paragraph(title, section_style))
        story.append(_table(normalized_rows))
        story.append(Spacer(1, 4 * mm))
        row_count += max(0, len(normalized_rows) - 1)

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="RutaCore - Reporte operacional",
    )
    doc.build(story)
    return buffer.getvalue(), row_count
