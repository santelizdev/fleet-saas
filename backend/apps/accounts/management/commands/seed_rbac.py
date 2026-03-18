from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Capability, Role, RoleCapability, UserRole
from apps.companies.models import Company


CAPABILITIES = {
    "vehicle.read": "Ver vehiculos",
    "vehicle.manage": "Crear/editar vehiculos",
    "doc.read": "Ver documentos",
    "doc.manage": "Gestionar documentos",
    "expense.read": "Ver gastos",
    "expense.report": "Reportar gastos",
    "expense.approve": "Aprobar/rechazar gastos",
    "expense.pay": "Marcar gastos como pagados",
    "maintenance.read": "Ver mantenciones",
    "maintenance.manage": "Gestionar mantenciones",
    "report.read": "Ver reportes",
}

ROLE_CAPS = {
    "Driver": [
        "vehicle.read",
        "doc.read",
        "expense.report",
    ],
    "Piloto": [
        "vehicle.read",
        "doc.read",
        "expense.report",
    ],
    "FleetManager": [
        "vehicle.read",
        "vehicle.manage",
        "doc.read",
        "doc.manage",
        "maintenance.read",
        "maintenance.manage",
        "expense.read",
        "expense.approve",
    ],
    "AdminCompany": list(CAPABILITIES.keys()),
    "Accounting": [
        "expense.read",
        "expense.approve",
        "expense.pay",
        "report.read",
    ],
}


class Command(BaseCommand):
    help = "Crea capabilities/roles base y asigna roles iniciales por empresa."

    def add_arguments(self, parser):
        parser.add_argument(
            "--company-id",
            type=int,
            help="Seed solo para una empresa especifica.",
        )
        parser.add_argument(
            "--skip-user-assignment",
            action="store_true",
            help="No asigna roles a usuarios existentes.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        company_id = options.get("company_id")
        skip_user_assignment = options.get("skip_user_assignment", False)

        cap_map = {}
        for code, description in CAPABILITIES.items():
            cap, _ = Capability.objects.get_or_create(
                code=code,
                defaults={"description": description},
            )
            if cap.description != description:
                cap.description = description
                cap.save(update_fields=["description"])
            cap_map[code] = cap

        companies = Company.objects.all().order_by("id")
        if company_id:
            companies = companies.filter(id=company_id)

        if not companies.exists():
            self.stdout.write(self.style.WARNING("No hay companies para seedear RBAC."))
            return

        for company in companies:
            role_map = {}
            for role_name, role_caps in ROLE_CAPS.items():
                role, _ = Role.objects.get_or_create(
                    company=company,
                    name=role_name,
                    defaults={"description": f"Rol base {role_name}"},
                )
                role_map[role_name] = role

                for cap_code in role_caps:
                    RoleCapability.objects.get_or_create(
                        role=role,
                        capability=cap_map[cap_code],
                    )

            if skip_user_assignment:
                continue

            admin_role = role_map["AdminCompany"]
            driver_role = role_map["Driver"]

            users = company.users.all().order_by("id")
            for user in users:
                if user.is_staff or user.is_superuser:
                    UserRole.objects.get_or_create(user=user, role=admin_role)
                elif not UserRole.objects.filter(user=user).exists():
                    # Fallback para dejar cuenta operativa desde el primer día.
                    UserRole.objects.get_or_create(user=user, role=driver_role)

            self.stdout.write(self.style.SUCCESS(f"RBAC seedeado para company {company.id}"))

