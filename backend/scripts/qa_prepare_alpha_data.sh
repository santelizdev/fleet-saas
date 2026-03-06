#!/usr/bin/env bash
set -euo pipefail

QA_EMAIL=${QA_EMAIL:-qa-admin@fleet.local}
QA_PASSWORD=${QA_PASSWORD:-QaPass123!}
QA_COMPANY_RUT=${QA_COMPANY_RUT:-99.100.100-1}
QA_COMPANY_NAME=${QA_COMPANY_NAME:-QA Fleet Company}
QA_VEHICLE_PLATE=${QA_VEHICLE_PLATE:-QA-1001}

# Prepara data mínima para QA y deja todo en una sola empresa.
docker compose run --rm web python manage.py shell -c "
from datetime import date
from django.contrib.auth import get_user_model
from apps.companies.models import Company
from apps.vehicles.models import Vehicle
from apps.accounts.models import Capability, Role, RoleCapability, UserRole

email='${QA_EMAIL}'
password='${QA_PASSWORD}'
rut='${QA_COMPANY_RUT}'
company_name='${QA_COMPANY_NAME}'
plate='${QA_VEHICLE_PLATE}'

company, _ = Company.objects.get_or_create(
    rut=rut,
    defaults={'name': company_name, 'plan': 'trial', 'status': Company.STATUS_ACTIVE}
)

User = get_user_model()
user, created = User.objects.get_or_create(
    email=email,
    defaults={'name': 'QA Admin', 'company': company, 'is_active': True, 'is_staff': True}
)
if not created:
    user.company = company
    user.is_staff = True
    user.is_active = True

user.set_password(password)
user.save()

caps = [
    'doc.read', 'doc.manage',
    'report.read',
    'vehicle.read', 'vehicle.manage',
    'expense.read', 'expense.report', 'expense.approve', 'expense.pay'
]
cap_objs = []
for code in caps:
    cap, _ = Capability.objects.get_or_create(code=code, defaults={'description': code})
    cap_objs.append(cap)

role, _ = Role.objects.get_or_create(company=company, name='QA AdminCompany', defaults={'description': 'QA role'})
for cap in cap_objs:
    RoleCapability.objects.get_or_create(role=role, capability=cap)
UserRole.objects.get_or_create(user=user, role=role)

vehicle, _ = Vehicle.objects.get_or_create(
    company=company,
    plate=plate,
    defaults={'status': Vehicle.STATUS_ACTIVE, 'brand': 'QA', 'model': 'MVP', 'current_km': 1000, 'assigned_driver': user}
)

if vehicle.assigned_driver_id is None:
    vehicle.assigned_driver = user
    vehicle.save(update_fields=['assigned_driver'])

print(f'QA_READY company_id={company.id} user_email={user.email} vehicle_id={vehicle.id} vehicle_plate={vehicle.plate}')
"
