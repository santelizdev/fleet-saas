from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from apps.accounts.admin import DriverAdmin, UserAdmin
from apps.accounts.forms import UserAdminCreationForm
from apps.accounts.models import Driver, Role, User, UserRole
from apps.companies.models import Company


class UserAdminFormTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Admin Company", rut="10.111.222-3")
        self.factory = RequestFactory()
        self.site = AdminSite()

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

    def test_popup_add_view_renders_for_superuser(self):
        superuser = User.objects.create_superuser(
            email="superadmin@test.local",
            password="Secret123!",
            name="Super Admin",
            company=self.company,
        )
        self.client.force_login(superuser)
        response = self.client.get(
            reverse("admin:accounts_user_add"),
            {"_popup": 1, "_to_field": "id"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirmación de contraseña")
        self.assertContains(response, "Empresa")

    def test_user_admin_excludes_driver_profiles(self):
        superuser = User.objects.create_superuser(
            email="superadmin-filter@test.local",
            password="Secret123!",
            name="Super Admin Filter",
            company=self.company,
        )
        driver = User.objects.create_user(
            email="driver-filter@test.local",
            password="Secret123!",
            name="Driver Filter",
            company=self.company,
        )
        role = Role.objects.create(company=self.company, name="Driver")
        UserRole.objects.create(user=driver, role=role)

        request = self.factory.get("/admin/accounts/user/")
        request.user = superuser

        queryset = UserAdmin(User, self.site).get_queryset(request)
        self.assertNotIn(driver.id, list(queryset.values_list("id", flat=True)))

    def test_driver_admin_only_lists_driver_profiles(self):
        superuser = User.objects.create_superuser(
            email="superadmin-driver@test.local",
            password="Secret123!",
            name="Super Admin Driver",
            company=self.company,
        )
        driver = User.objects.create_user(
            email="driver-only@test.local",
            password="Secret123!",
            name="Driver Only",
            company=self.company,
        )
        office_user = User.objects.create_user(
            email="office@test.local",
            password="Secret123!",
            name="Office User",
            company=self.company,
        )
        role = Role.objects.create(company=self.company, name="Driver")
        UserRole.objects.create(user=driver, role=role)

        request = self.factory.get("/admin/accounts/driver/")
        request.user = superuser

        queryset = DriverAdmin(Driver, self.site).get_queryset(request)
        ids = list(queryset.values_list("id", flat=True))
        self.assertIn(driver.id, ids)
        self.assertNotIn(office_user.id, ids)


class UserRoleValidationTest(TestCase):
    def test_user_role_requires_same_company(self):
        company_a = Company.objects.create(name="Company A", rut="11.111.111-1")
        company_b = Company.objects.create(name="Company B", rut="22.222.222-2")
        user = User.objects.create_user(email="user@local.dev", password="Secret123!", name="User", company=company_a)
        role = Role.objects.create(company=company_b, name="Piloto")

        with self.assertRaisesMessage(ValidationError, "misma company"):
            UserRole.objects.create(user=user, role=role)
