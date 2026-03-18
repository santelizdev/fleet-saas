import shutil
import tempfile
from datetime import date
from io import BytesIO

from django.core.exceptions import ValidationError
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils.functional import empty
from rest_framework import status
from rest_framework.test import APITestCase
from PIL import Image

from apps.accounts.models import Capability, Role, RoleCapability, User, UserRole
from apps.audit.models import AuditLog
from apps.companies.models import Company
from apps.documents.models import Attachment
from apps.expenses.models import ExpenseCategory, VehicleExpense
from apps.product_analytics.models import ProductEvent
from apps.vehicles.models import Vehicle


def make_test_upload(name="expense.png", image_format="PNG", size=(2200, 1400), color=(255, 180, 0)):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format=image_format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{image_format.lower()}")


class ExpensesWorkflowAPITest(APITestCase):
    def setUp(self):
        self.previous_media_root = settings.MEDIA_ROOT
        self.media_root = tempfile.mkdtemp(prefix="fleet-expense-tests-")
        settings.MEDIA_ROOT = self.media_root
        default_storage._wrapped = empty
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

    def tearDown(self):
        settings.MEDIA_ROOT = self.previous_media_root
        default_storage._wrapped = empty
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

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
            "support_image": make_test_upload(),
        }
        create_resp = self.client.post(create_url, payload, format="multipart")
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        expense_id = create_resp.data["id"]
        self.assertEqual(create_resp.data["support_attachment"]["mime_type"], "image/jpeg")
        self.assertEqual(Attachment.objects.count(), 1)

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


class ExpenseModelValidationTest(APITestCase):
    def test_vehicle_expense_rejects_category_from_other_company(self):
        company_a = Company.objects.create(name="Expense A", rut="55.555.555-5")
        company_b = Company.objects.create(name="Expense B", rut="66.666.666-6")
        reporter = User.objects.create_user(email="reporter@local.dev", password="Secret123!", name="Reporter", company=company_a)
        vehicle = Vehicle.objects.create(company=company_a, plate="ZZ11ZZ")
        category = ExpenseCategory.objects.create(company=company_b, name="Other")

        with self.assertRaisesMessage(ValidationError, "misma company"):
            VehicleExpense.objects.create(
                company=company_a,
                vehicle=vehicle,
                category=category,
                amount_clp=1000,
                expense_date=date.today(),
                reported_by=reporter,
            )
