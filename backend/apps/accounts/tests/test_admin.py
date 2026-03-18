from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.forms import UserAdminCreationForm
from apps.accounts.models import Role, User, UserRole
from apps.companies.models import Company


class UserAdminFormTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Admin Company", rut="10.111.222-3")

    def test_creation_form_hashes_password(self):
        form = UserAdminCreationForm(
            data={
                "email": "nuevo@local.dev",
                "name": "Nuevo Usuario",
                "phone": "",
                "company": self.company.id,
                "is_active": True,
                "is_staff": False,
                "password1": "Secret123!",
                "password2": "Secret123!",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertNotEqual(user.password, "Secret123!")
        self.assertTrue(user.check_password("Secret123!"))


class UserRoleValidationTest(TestCase):
    def test_user_role_requires_same_company(self):
        company_a = Company.objects.create(name="Company A", rut="11.111.111-1")
        company_b = Company.objects.create(name="Company B", rut="22.222.222-2")
        user = User.objects.create_user(email="user@local.dev", password="Secret123!", name="User", company=company_a)
        role = Role.objects.create(company=company_b, name="Piloto")

        with self.assertRaisesMessage(ValidationError, "misma company"):
            UserRole.objects.create(user=user, role=role)

