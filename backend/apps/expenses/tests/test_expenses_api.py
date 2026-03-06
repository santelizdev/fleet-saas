from datetime import date

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Capability, Role, RoleCapability, User, UserRole
from apps.audit.models import AuditLog
from apps.companies.models import Company
from apps.documents.models import Attachment
from apps.expenses.models import VehicleExpense
from apps.product_analytics.models import ProductEvent
from apps.vehicles.models import Vehicle


class ExpensesWorkflowAPITest(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Expense Co", rut="71.222.333-4")
        self.driver = User.objects.create_user(email="driver@expense.local", password="Secret123!", name="Driver", company=self.company)
        self.manager = User.objects.create_user(email="manager@expense.local", password="Secret123!", name="Manager", company=self.company)
        self.accounting = User.objects.create_user(email="accounting@expense.local", password="Secret123!", name="Accounting", company=self.company)
        self.vehicle = Vehicle.objects.create(company=self.company, plate="EX-1001")

        c_report, _ = Capability.objects.get_or_create(code="expense.report")
        c_approve, _ = Capability.objects.get_or_create(code="expense.approve")
        c_pay, _ = Capability.objects.get_or_create(code="expense.pay")
        c_read, _ = Capability.objects.get_or_create(code="expense.read")

        r_driver = Role.objects.create(company=self.company, name="DriverRole")
        RoleCapability.objects.create(role=r_driver, capability=c_report)
        UserRole.objects.create(user=self.driver, role=r_driver)

        r_manager = Role.objects.create(company=self.company, name="ManagerRole")
        RoleCapability.objects.create(role=r_manager, capability=c_approve)
        RoleCapability.objects.create(role=r_manager, capability=c_read)
        UserRole.objects.create(user=self.manager, role=r_manager)

        r_acc = Role.objects.create(company=self.company, name="AccountingRole")
        RoleCapability.objects.create(role=r_acc, capability=c_pay)
        RoleCapability.objects.create(role=r_acc, capability=c_read)
        UserRole.objects.create(user=self.accounting, role=r_acc)

    def test_report_approve_pay_with_attachment(self):
        self.client.force_authenticate(self.driver)
        create_url = reverse("vehicle-expense-list")
        payload = {
            "vehicle": self.vehicle.id,
            "amount_clp": 120000,
            "expense_date": str(date.today()),
            "supplier": "Copec",
            "km": 1100,
            "invoice_number": "F-001",
        }
        create_resp = self.client.post(create_url, payload, format="json")
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        expense_id = create_resp.data["id"]

        attach = Attachment.objects.create(
            company=self.company,
            storage_key="expense/proof-1.pdf",
            size_bytes=100,
            mime_type="application/pdf",
        )
        attach_url = reverse("vehicle-expense-attachment-list")
        attach_resp = self.client.post(
            attach_url,
            {"vehicle_expense": expense_id, "attachment": attach.id},
            format="json",
        )
        self.assertEqual(attach_resp.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(self.manager)
        approve_url = reverse("vehicle-expense-approve", kwargs={"pk": expense_id})
        approve_resp = self.client.post(approve_url)
        self.assertEqual(approve_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(approve_resp.data["approval_status"], VehicleExpense.APPROVAL_APPROVED)

        self.client.force_authenticate(self.accounting)
        pay_url = reverse("vehicle-expense-pay", kwargs={"pk": expense_id})
        pay_resp = self.client.post(pay_url)
        self.assertEqual(pay_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(pay_resp.data["payment_status"], VehicleExpense.PAYMENT_PAID)

        self.assertTrue(AuditLog.objects.filter(company=self.company, action="expense.report").exists())
        self.assertTrue(AuditLog.objects.filter(company=self.company, action="expense.approve").exists())
        self.assertTrue(AuditLog.objects.filter(company=self.company, action="expense.pay").exists())
        self.assertTrue(ProductEvent.objects.filter(company=self.company, event_name="expense_reported").exists())
        self.assertTrue(ProductEvent.objects.filter(company=self.company, event_name="expense_approved").exists())

    def test_cannot_pay_non_approved(self):
        self.client.force_authenticate(self.driver)
        create_resp = self.client.post(
            reverse("vehicle-expense-list"),
            {"vehicle": self.vehicle.id, "amount_clp": 1000, "expense_date": str(date.today())},
            format="json",
        )
        expense_id = create_resp.data["id"]

        self.client.force_authenticate(self.accounting)
        pay_url = reverse("vehicle-expense-pay", kwargs={"pk": expense_id})
        pay_resp = self.client.post(pay_url)
        self.assertEqual(pay_resp.status_code, status.HTTP_400_BAD_REQUEST)
