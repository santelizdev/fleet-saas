"""Puebla una empresa con datos demo coherentes para revisar el backoffice local."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, User, UserRole
from apps.alerts.models import AlertState, DocumentAlert, JobRun, MaintenanceAlert, Notification
from apps.audit.models import AuditLog
from apps.companies.models import Branch, Company, CompanyLimit
from apps.documents.models import DriverLicense, VehicleDocument
from apps.expenses.models import ExpenseCategory, VehicleExpense
from apps.maintenance.models import MaintenanceRecord, VehicleOdometerLog
from apps.product_analytics.models import ProductEvent
from apps.reports.models import ReportExportLog
from apps.tags.models import TagCharge, TagImportBatch, TagTransit, TollGate, TollRoad
from apps.vehicles.models import Vehicle


DEMO_PASSWORD = "demo1234"
DEMO_MARKER = "[seed-demo]"


@dataclass(frozen=True)
class DemoUsers:
    """Agrupa los usuarios que el comando necesita reutilizar entre módulos."""

    fleet_manager: User
    accounting: User
    drivers: list[User]


class Command(BaseCommand):
    help = "Genera contenido demo para flota, documentos, gastos, alertas, reportes, actividad y TAG."

    def add_arguments(self, parser):
        parser.add_argument("--company-id", type=int, help="Usa una empresa existente en vez de crear/reusar la demo.")
        parser.add_argument(
            "--company-name",
            default="Fleet Demo QA",
            help="Nombre de la empresa demo cuando no se especifica --company-id.",
        )
        parser.add_argument(
            "--company-rut",
            default="76.555.000-1",
            help="RUT de la empresa demo cuando no se especifica --company-id.",
        )
        parser.add_argument("--drivers", type=int, default=6, help="Cantidad de conductores demo a generar.")
        parser.add_argument("--vehicles", type=int, default=12, help="Cantidad de vehículos demo a generar.")
        parser.add_argument("--seed", type=int, default=42, help="Seed para mantener datos reproducibles.")
        parser.add_argument("--skip-tags", action="store_true", help="Omite la carga del módulo TAG / pórticos.")

    @transaction.atomic
    def handle(self, *args, **options):
        company = self._resolve_company(options)
        rng = random.Random(options["seed"] + company.id)

        CompanyLimit.objects.get_or_create(company=company)
        call_command("seed_rbac", company_id=company.id, skip_user_assignment=True)

        branches = self._seed_branches(company)
        categories = self._seed_categories(company)
        users = self._seed_users(company, max(1, options["drivers"]))
        self._assign_roles(company, users)
        vehicles = self._seed_vehicles(company, branches, users.drivers, max(1, options["vehicles"]), rng)
        self._seed_odometer_logs(company, vehicles, users.fleet_manager)
        driver_licenses = self._seed_driver_licenses(company, users.drivers, users.fleet_manager, rng)
        vehicle_documents = self._seed_vehicle_documents(company, vehicles, users.fleet_manager, rng)
        maintenance_records = self._seed_maintenance(company, vehicles, users.fleet_manager, rng)
        self._seed_expenses(company, vehicles, categories, users, rng)
        self._seed_alerts_and_notifications(company, vehicle_documents, driver_licenses, maintenance_records)
        self._seed_reports(company, users)
        self._seed_product_events(company, users, vehicles)
        self._seed_audit_logs(company, users, vehicles)
        if not options["skip_tags"]:
            self._seed_tags(company, vehicles, users.fleet_manager, rng)
        self._seed_job_runs()

        self.stdout.write(self.style.SUCCESS(f"Empresa demo lista: {company.name} (id={company.id})"))
        self.stdout.write("Credenciales demo útiles para navegar APIs internas si luego las necesitas:")
        self.stdout.write(f"- password común usuarios demo: {DEMO_PASSWORD}")
        self.stdout.write(f"- fleet manager: manager+company{company.id}@fleet.local")
        self.stdout.write(f"- accounting: accounting+company{company.id}@fleet.local")
        self.stdout.write(f"- primer conductor: driver01+company{company.id}@fleet.local")

    def _resolve_company(self, options) -> Company:
        company_id = options.get("company_id")
        if company_id:
            company = Company.objects.filter(id=company_id).first()
            if company is None:
                raise CommandError(f"No existe la empresa id={company_id}.")
            return company

        company, created = Company.objects.get_or_create(
            rut=options["company_rut"],
            defaults={
                "name": options["company_name"],
                "plan": "growth",
                "status": Company.STATUS_ACTIVE,
            },
        )
        if not created and company.name != options["company_name"]:
            company.name = options["company_name"]
            company.save(update_fields=["name"])
        return company

    def _seed_branches(self, company: Company) -> list[Branch]:
        branch_defs = [
            ("Casa Matriz", "Santiago Centro", "CC-001"),
            ("Operación Norte", "Huechuraba", "CC-002"),
            ("Operación Sur", "San Bernardo", "CC-003"),
        ]
        branches: list[Branch] = []
        for name, address, cost_center_code in branch_defs:
            branch, _ = Branch.objects.update_or_create(
                company=company,
                name=name,
                defaults={"address": address, "cost_center_code": cost_center_code},
            )
            branches.append(branch)
        return branches

    def _seed_categories(self, company: Company) -> list[ExpenseCategory]:
        category_defs = [
            ("Combustible", "Carga de bencina y diesel."),
            ("Peajes", "Gastos manuales de TAG y peajes."),
            ("Neumáticos", "Cambio y reparación de neumáticos."),
            ("Mantención", "Servicios preventivos y correctivos."),
            ("Lavado", "Lavado exterior e interior."),
            ("Imprevistos", "Gastos menores no planificados."),
        ]
        categories: list[ExpenseCategory] = []
        for name, description in category_defs:
            category, _ = ExpenseCategory.objects.update_or_create(
                company=company,
                name=name,
                defaults={"description": f"{description} {DEMO_MARKER}"},
            )
            categories.append(category)
        return categories

    def _seed_users(self, company: Company, driver_count: int) -> DemoUsers:
        manager = self._upsert_user(
            company=company,
            email=f"manager+company{company.id}@fleet.local",
            name="Jefa de Flota Demo",
            phone="+56 9 1111 1111",
        )
        accounting = self._upsert_user(
            company=company,
            email=f"accounting+company{company.id}@fleet.local",
            name="Finanzas Demo",
            phone="+56 9 2222 2222",
        )
        drivers = []
        for index in range(1, driver_count + 1):
            drivers.append(
                self._upsert_user(
                    company=company,
                    email=f"driver{index:02d}+company{company.id}@fleet.local",
                    name=f"Conductor Demo {index:02d}",
                    phone=f"+56 9 30{index:02d} {index:04d}",
                )
            )
        return DemoUsers(fleet_manager=manager, accounting=accounting, drivers=drivers)

    def _upsert_user(self, *, company: Company, email: str, name: str, phone: str) -> User:
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(
                email=email,
                password=DEMO_PASSWORD,
                name=name,
                phone=phone,
                company=company,
            )
            return user

        changed_fields: list[str] = []
        if user.company_id != company.id:
            user.company = company
            changed_fields.append("company")
        if user.name != name:
            user.name = name
            changed_fields.append("name")
        if user.phone != phone:
            user.phone = phone
            changed_fields.append("phone")
        if not user.is_active:
            user.is_active = True
            changed_fields.append("is_active")
        if changed_fields:
            user.save(update_fields=changed_fields)
        user.set_password(DEMO_PASSWORD)
        user.save(update_fields=["password"])
        return user

    def _assign_roles(self, company: Company, users: DemoUsers) -> None:
        roles = {role.name: role for role in Role.objects.filter(company=company)}
        if not roles:
            raise CommandError("No se pudieron cargar roles base. Ejecuta seed_rbac primero.")

        UserRole.objects.get_or_create(user=users.fleet_manager, role=roles["FleetManager"])
        UserRole.objects.get_or_create(user=users.accounting, role=roles["Accounting"])
        for driver in users.drivers:
            UserRole.objects.get_or_create(user=driver, role=roles["Driver"])

    def _seed_vehicles(
        self,
        company: Company,
        branches: list[Branch],
        drivers: list[User],
        vehicle_count: int,
        rng: random.Random,
    ) -> list[Vehicle]:
        brand_models = [
            ("Toyota", "Hilux"),
            ("Maxus", "T60"),
            ("Mitsubishi", "L200"),
            ("Hyundai", "Porter"),
            ("Peugeot", "Partner"),
        ]
        vehicles: list[Vehicle] = []
        for index in range(1, vehicle_count + 1):
            brand, model = brand_models[(index - 1) % len(brand_models)]
            plate = f"Q{company.id % 10}{index:03d}ST"
            vehicle, _ = Vehicle.objects.update_or_create(
                company=company,
                plate=plate,
                defaults={
                    "branch": branches[(index - 1) % len(branches)],
                    "brand": brand,
                    "model": model,
                    "year": 2019 + (index % 6),
                    "vin": f"{company.id:02d}VIN{index:08d}",
                    "engine_number": f"ENG{company.id:02d}{index:06d}",
                    "current_km": 18_000 + index * 4_500 + rng.randint(0, 2_000),
                    "status": Vehicle.STATUS_ACTIVE if index % 6 else Vehicle.STATUS_INACTIVE,
                    "assigned_driver": drivers[(index - 1) % len(drivers)],
                },
            )
            vehicles.append(vehicle)
        return vehicles

    def _seed_odometer_logs(self, company: Company, vehicles: list[Vehicle], actor: User) -> None:
        km_steps = [
            (90, 12_000),
            (60, 8_000),
            (30, 3_500),
            (7, 0),
        ]
        today = timezone.localdate()
        for vehicle in vehicles:
            for days_ago, delta in km_steps:
                km = max(500, vehicle.current_km - delta)
                self._get_or_create(
                    VehicleOdometerLog,
                    company=company,
                    vehicle=vehicle,
                    km=km,
                    source=VehicleOdometerLog.SOURCE_MANUAL,
                    defaults={
                        "recorded_by": actor,
                        "note": f"Lectura demo {today - timedelta(days=days_ago)} {DEMO_MARKER}",
                    },
                )

    def _seed_driver_licenses(
        self,
        company: Company,
        drivers: list[User],
        actor: User,
        rng: random.Random,
    ) -> list[DriverLicense]:
        today = timezone.localdate()
        licenses: list[DriverLicense] = []
        categories = ["A2", "A3", "B", "A4"]
        for index, driver in enumerate(drivers, start=1):
            expiry_date = today + timedelta(days=15 + index * 18 + rng.randint(-5, 10))
            license_obj, _ = DriverLicense.objects.update_or_create(
                company=company,
                driver=driver,
                license_number=f"LIC-{company.id:02d}-{index:04d}",
                is_current=True,
                defaults={
                    "category": categories[(index - 1) % len(categories)],
                    "issue_date": expiry_date - timedelta(days=365 * 4),
                    "expiry_date": expiry_date,
                    "reminder_days_before": 30,
                    "status": DriverLicense.STATUS_ACTIVE if expiry_date >= today else DriverLicense.STATUS_EXPIRED,
                    "created_by": actor,
                },
            )
            licenses.append(license_obj)
        return licenses

    def _seed_vehicle_documents(
        self,
        company: Company,
        vehicles: list[Vehicle],
        actor: User,
        rng: random.Random,
    ) -> list[VehicleDocument]:
        today = timezone.localdate()
        type_offsets = {
            VehicleDocument.TYPE_PERMISO_CIRCULACION: 45,
            VehicleDocument.TYPE_REVISION_TECNICA: 20,
            VehicleDocument.TYPE_SEGURO: 10,
            VehicleDocument.TYPE_GASES: 60,
        }
        documents: list[VehicleDocument] = []
        for index, vehicle in enumerate(vehicles, start=1):
            for doc_type, base_offset in type_offsets.items():
                expiry_date = today + timedelta(days=base_offset - (index % 5) * 7 + rng.randint(-3, 4))
                status = VehicleDocument.STATUS_ACTIVE if expiry_date >= today else VehicleDocument.STATUS_EXPIRED
                document = self._upsert_single_record(
                    VehicleDocument,
                    {
                        "company": company,
                        "vehicle": vehicle,
                        "type": doc_type,
                        "is_current": True,
                    },
                    {
                        "issue_date": expiry_date - timedelta(days=330),
                        "expiry_date": expiry_date,
                        "reminder_days_before": 30,
                        "status": status,
                        "notes": f"Documento demo para revisar vencimientos. {DEMO_MARKER}",
                        "created_by": actor,
                    },
                )
                documents.append(document)
        return documents

    def _seed_maintenance(
        self,
        company: Company,
        vehicles: list[Vehicle],
        actor: User,
        rng: random.Random,
    ) -> list[MaintenanceRecord]:
        today = timezone.localdate()
        records: list[MaintenanceRecord] = []
        for index, vehicle in enumerate(vehicles, start=1):
            completed = self._upsert_single_record(
                MaintenanceRecord,
                {
                    "company": company,
                    "vehicle": vehicle,
                    "description": f"Mantención preventiva {index:02d} {DEMO_MARKER}",
                },
                {
                    "type": MaintenanceRecord.TYPE_PREVENTIVE,
                    "status": MaintenanceRecord.STATUS_COMPLETED,
                    "service_date": today - timedelta(days=50 + (index % 4) * 10),
                    "odometer_km": max(1_000, vehicle.current_km - 2_500),
                    "cost_clp": 180_000 + (index % 3) * 35_000,
                    "next_due_date": today + timedelta(days=10 + (index % 5) * 7),
                    "next_due_km": vehicle.current_km + 1_500 + index * 120,
                    "created_by": actor,
                },
            )
            records.append(completed)

            open_record = self._upsert_single_record(
                MaintenanceRecord,
                {
                    "company": company,
                    "vehicle": vehicle,
                    "description": f"Inspección correctiva {index:02d} {DEMO_MARKER}",
                },
                {
                    "type": MaintenanceRecord.TYPE_CORRECTIVE,
                    "status": MaintenanceRecord.STATUS_OPEN,
                    "service_date": today - timedelta(days=rng.randint(1, 7)),
                    "odometer_km": vehicle.current_km - rng.randint(0, 400),
                    "cost_clp": 90_000 + (index % 4) * 22_000,
                    "next_due_date": today + timedelta(days=5 + (index % 6) * 4),
                    "next_due_km": vehicle.current_km + 800 + index * 90,
                    "created_by": actor,
                },
            )
            records.append(open_record)
        return records

    def _seed_expenses(
        self,
        company: Company,
        vehicles: list[Vehicle],
        categories: list[ExpenseCategory],
        users: DemoUsers,
        rng: random.Random,
    ) -> None:
        today = timezone.localdate()
        for vehicle_index, vehicle in enumerate(vehicles, start=1):
            for expense_index in range(1, 4):
                approval_status = VehicleExpense.APPROVAL_REPORTED
                payment_status = VehicleExpense.PAYMENT_UNPAID
                approved_by = None
                paid_by = None
                if expense_index >= 2:
                    approval_status = VehicleExpense.APPROVAL_APPROVED
                    approved_by = users.fleet_manager
                if expense_index == 3:
                    payment_status = VehicleExpense.PAYMENT_PAID
                    paid_by = users.accounting

                invoice_number = f"DEM-{company.id:02d}-{vehicle_index:03d}-{expense_index}"
                self._upsert_single_record(
                    VehicleExpense,
                    {
                        "company": company,
                        "invoice_number": invoice_number,
                    },
                    {
                        "vehicle": vehicle,
                        "category": categories[(vehicle_index + expense_index - 2) % len(categories)],
                        "amount_clp": 38_000 + vehicle_index * 4_500 + expense_index * 12_000,
                        "expense_date": today - timedelta(days=expense_index * 6 + rng.randint(0, 3)),
                        "supplier": ["Copec", "Shell", "Derco", "ProntoWash"][expense_index % 4],
                        "km": max(1_000, vehicle.current_km - expense_index * 250),
                        "notes": f"Gasto demo para poblar dashboard financiero. {DEMO_MARKER}",
                        "approval_status": approval_status,
                        "payment_status": payment_status,
                        "reported_by": vehicle.assigned_driver or users.fleet_manager,
                        "approved_by": approved_by,
                        "paid_by": paid_by,
                    },
                )

    def _seed_alerts_and_notifications(
        self,
        company: Company,
        vehicle_documents: list[VehicleDocument],
        driver_licenses: list[DriverLicense],
        maintenance_records: list[MaintenanceRecord],
    ) -> None:
        today = timezone.localdate()

        for document in vehicle_documents:
            if document.expiry_date > today + timedelta(days=40):
                continue
            alert, _ = DocumentAlert.objects.get_or_create(
                company=company,
                vehicle_document=document,
                kind=DocumentAlert.KIND_EXPIRY,
                due_date=document.expiry_date,
                scheduled_for=document.expiry_date - timedelta(days=document.reminder_days_before),
                defaults={
                    "state": AlertState.PENDING,
                    "message": f"{document.get_type_display()} próximo a vencer para {document.vehicle.plate}. {DEMO_MARKER}",
                },
            )
            self._seed_notification(company, document_alert=alert, maintenance_alert=None)

        for license_obj in driver_licenses:
            if license_obj.expiry_date > today + timedelta(days=45):
                continue
            alert, _ = DocumentAlert.objects.get_or_create(
                company=company,
                driver_license=license_obj,
                kind=DocumentAlert.KIND_EXPIRY,
                due_date=license_obj.expiry_date,
                scheduled_for=license_obj.expiry_date - timedelta(days=license_obj.reminder_days_before),
                defaults={
                    "state": AlertState.PENDING,
                    "message": f"Licencia de {license_obj.driver.name} próxima a vencer. {DEMO_MARKER}",
                },
            )
            self._seed_notification(company, document_alert=alert, maintenance_alert=None)

        for record in maintenance_records:
            if record.status != MaintenanceRecord.STATUS_OPEN:
                continue
            if record.next_due_date:
                alert, _ = MaintenanceAlert.objects.get_or_create(
                    company=company,
                    vehicle=record.vehicle,
                    maintenance_record_ref=str(record.id),
                    kind=MaintenanceAlert.KIND_BY_DATE,
                    due_date=record.next_due_date,
                    defaults={
                        "state": AlertState.PENDING,
                        "message": f"Mantención pendiente por fecha en {record.vehicle.plate}. {DEMO_MARKER}",
                    },
                )
                self._seed_notification(company, document_alert=None, maintenance_alert=alert)

            if record.next_due_km:
                alert, _ = MaintenanceAlert.objects.get_or_create(
                    company=company,
                    vehicle=record.vehicle,
                    maintenance_record_ref=f"{record.id}-km",
                    kind=MaintenanceAlert.KIND_BY_KM,
                    due_km=record.next_due_km,
                    defaults={
                        "state": AlertState.PENDING,
                        "message": f"Mantención pendiente por kilometraje en {record.vehicle.plate}. {DEMO_MARKER}",
                    },
                )
                self._seed_notification(company, document_alert=None, maintenance_alert=alert)

    def _seed_notification(
        self,
        company: Company,
        *,
        document_alert: DocumentAlert | None,
        maintenance_alert: MaintenanceAlert | None,
    ) -> None:
        if document_alert is not None:
            lookup = {
                "company": company,
                "document_alert": document_alert,
                "channel": Notification.CHANNEL_IN_APP,
            }
            recipient = document_alert.message
        else:
            lookup = {
                "company": company,
                "maintenance_alert": maintenance_alert,
                "channel": Notification.CHANNEL_IN_APP,
            }
            recipient = maintenance_alert.message

        notification = Notification.objects.filter(**lookup).order_by("id").first()
        defaults = {
            "recipient": recipient,
            "status": Notification.STATUS_QUEUED,
            "attempts": 0,
            "last_error": "",
            "available_at": timezone.now(),
            "sent_at": None,
        }
        if notification is None:
            Notification.objects.create(**lookup, **defaults)
            return

        for field_name, value in defaults.items():
            setattr(notification, field_name, value)
        notification.save(update_fields=list(defaults.keys()))

    def _seed_reports(self, company: Company, users: DemoUsers) -> None:
        report_defs = [
            ("dashboard", ReportExportLog.FORMAT_CSV, ReportExportLog.STATUS_COMPLETED, 120),
            ("vehicle_costs", ReportExportLog.FORMAT_XLSX, ReportExportLog.STATUS_COMPLETED, 48),
            ("expense_book", ReportExportLog.FORMAT_CSV, ReportExportLog.STATUS_COMPLETED, 92),
            ("tag_summary", ReportExportLog.FORMAT_CSV, ReportExportLog.STATUS_REJECTED, 0),
        ]
        for index, (report_type, export_format, status, row_count) in enumerate(report_defs, start=1):
            self._upsert_single_record(
                ReportExportLog,
                {
                    "company": company,
                    "report_type": report_type,
                    "export_format": export_format,
                    "note": f"{DEMO_MARKER}-{index}",
                },
                {
                    "requested_by": users.accounting if index % 2 else users.fleet_manager,
                    "status": status,
                    "row_count": row_count,
                },
            )

    def _seed_product_events(self, company: Company, users: DemoUsers, vehicles: list[Vehicle]) -> None:
        secondary_vehicle = vehicles[1] if len(vehicles) > 1 else vehicles[0]
        event_defs = [
            ("dashboard.view", users.fleet_manager, {"summary": "Revisión matinal del tablero ejecutivo"}),
            ("vehicle.import.csv", users.fleet_manager, {"summary": "Carga inicial de flota para onboarding"}),
            ("expense.reported", users.drivers[0], {"summary": f"Gasto reportado para {vehicles[0].plate}"}),
            ("document.pack.created", users.fleet_manager, {"summary": f"Pack documental creado para {secondary_vehicle.plate}"}),
            ("report.exported", users.accounting, {"summary": "Exportación financiera del cierre semanal"}),
        ]
        for index, (event_name, actor, payload) in enumerate(event_defs, start=1):
            self._upsert_single_record(
                ProductEvent,
                {
                    "company": company,
                    "event_name": event_name,
                    "payload": {**payload, "marker": f"{DEMO_MARKER}-{index}"},
                },
                {
                    "actor": actor,
                },
            )

    def _seed_audit_logs(self, company: Company, users: DemoUsers, vehicles: list[Vehicle]) -> None:
        audit_defs = [
            ("vehicle.create", users.fleet_manager, "Vehicle", str(vehicles[0].id)),
            ("document.renew", users.fleet_manager, "VehicleDocument", str(vehicles[1].id)),
            ("expense.approve", users.accounting, "VehicleExpense", "finance-001"),
            ("maintenance.schedule", users.fleet_manager, "MaintenanceRecord", "maint-001"),
        ]
        for index, (action, actor, object_type, object_id) in enumerate(audit_defs, start=1):
            self._upsert_single_record(
                AuditLog,
                {
                    "company": company,
                    "action": action,
                    "object_type": object_type,
                    "object_id": object_id,
                },
                {
                    "actor": actor,
                    "before_json": {"marker": DEMO_MARKER, "step": index},
                    "after_json": {"marker": DEMO_MARKER, "step": index, "status": "ok"},
                },
            )

    def _seed_tags(self, company: Company, vehicles: list[Vehicle], actor: User, rng: random.Random) -> None:
        today = timezone.localdate()
        road_defs = [
            ("Costanera Norte", "CN", "Grupo Costanera"),
            ("Vespucio Sur", "VS", "Autopista Vespucio Sur"),
        ]
        roads: list[TollRoad] = []
        for name, code, operator_name in road_defs:
            road, _ = TollRoad.objects.update_or_create(
                company=company,
                name=name,
                defaults={"code": code, "operator_name": operator_name, "is_active": True},
            )
            roads.append(road)

        gates: list[TollGate] = []
        for index, road in enumerate(roads, start=1):
            for gate_number in range(1, 3):
                gate, _ = TollGate.objects.update_or_create(
                    company=company,
                    road=road,
                    code=f"{road.code}-{gate_number}",
                    defaults={
                        "name": f"Pórtico {gate_number} {road.name}",
                        "direction": "Norte-Sur" if gate_number % 2 else "Sur-Norte",
                        "km_marker": Decimal(f"{8 * index + gate_number}.50"),
                        "is_active": True,
                    },
                )
                gates.append(gate)

        batch = self._upsert_single_record(
            TagImportBatch,
            {
                "company": company,
                "source_name": "Proveedor Demo TAG",
                "source_file_name": f"tag-demo-company-{company.id}.csv",
            },
            {
                "period_start": today.replace(day=1),
                "period_end": today,
                "status": TagImportBatch.STATUS_PROCESSED,
                "notes": f"Lote demo para analítica TAG. {DEMO_MARKER}",
                "created_by": actor,
            },
        )

        for index, vehicle in enumerate(vehicles[: min(len(vehicles), 8)], start=1):
            gate = gates[(index - 1) % len(gates)]
            transit_at = timezone.now() - timedelta(days=index, hours=index)
            matched_vehicle = vehicle if index % 4 else None
            detected_plate = vehicle.plate if matched_vehicle else f"ZZ-{index:03d}"
            transit = self._upsert_single_record(
                TagTransit,
                {
                    "company": company,
                    "road": gate.road,
                    "gate": gate,
                    "transit_at": transit_at,
                },
                {
                    "batch": batch,
                    "vehicle": matched_vehicle,
                    "detected_plate": detected_plate,
                    "transit_date": transit_at.date(),
                    "amount_clp": 1_200 + index * 380,
                    "currency": "CLP",
                    "match_status": TagTransit.MATCH_MATCHED if matched_vehicle else TagTransit.MATCH_UNMATCHED,
                    "notes": f"Tránsito demo {DEMO_MARKER}",
                },
            )
            self._upsert_single_record(
                TagCharge,
                {
                    "company": company,
                    "road": gate.road,
                    "gate": gate,
                    "charge_date": transit.transit_date,
                    "detected_plate": detected_plate,
                },
                {
                    "transit": transit,
                    "batch": batch,
                    "vehicle": matched_vehicle,
                    "billed_at": transit_at + timedelta(hours=4),
                    "amount_clp": transit.amount_clp + rng.randint(50, 240),
                    "status": TagCharge.STATUS_RECONCILED if matched_vehicle else TagCharge.STATUS_UNMATCHED,
                    "notes": f"Cobro demo {DEMO_MARKER}",
                },
            )

    def _seed_job_runs(self) -> None:
        now = timezone.now()
        job_defs = [
            ("generate_daily_alerts", JobRun.STATUS_SUCCESS, {"created_alerts": 8}),
            ("process_notifications", JobRun.STATUS_SUCCESS, {"sent": 10, "failed": 1}),
        ]
        for index, (job_name, status, details) in enumerate(job_defs, start=1):
            self._upsert_single_record(
                JobRun,
                {
                    "job_name": job_name,
                    "details": {**details, "marker": f"{DEMO_MARKER}-{index}"},
                },
                {
                    "status": status,
                    "started_at": now - timedelta(minutes=30 * index),
                    "finished_at": now - timedelta(minutes=30 * index - 2),
                },
            )

    def _get_or_create(self, model, **kwargs):
        defaults = kwargs.pop("defaults", {})
        return model.objects.get_or_create(defaults=defaults, **kwargs)

    def _upsert_single_record(self, model, lookup: dict, defaults: dict):
        """Actualiza el primer match para poder re-ejecutar el comando sin inflar duplicados demo."""
        obj = model.objects.filter(**lookup).order_by("id").first()
        if obj is None:
            return model.objects.create(**lookup, **defaults)

        changed_fields: list[str] = []
        for field_name, value in defaults.items():
            if getattr(obj, field_name) != value:
                setattr(obj, field_name, value)
                changed_fields.append(field_name)
        if changed_fields:
            obj.save(update_fields=changed_fields)
        return obj
