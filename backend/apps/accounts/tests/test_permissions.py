from django.test import TestCase

from apps.accounts.models import Capability, Role, RoleCapability, User, UserRole
from apps.accounts.permissions import user_has_capability
from apps.companies.models import Company


class CapabilityPermissionTest(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(name="Company A", rut="33.333.333-3")
        self.company_b = Company.objects.create(name="Company B", rut="44.444.444-4")

        self.user_a = User.objects.create_user(
            email="user-a@local.dev",
            password="Secret123!",
            name="User A",
            company=self.company_a,
        )

    def test_user_has_capability_true_only_when_assigned_in_same_company(self):
        cap = Capability.objects.create(code="vehicle.read", description="Read vehicles")

        role_b = Role.objects.create(company=self.company_b, name="FleetManager")
        RoleCapability.objects.create(role=role_b, capability=cap)
        UserRole.objects.create(user=self.user_a, role=role_b)

        self.assertFalse(
            user_has_capability(self.user_a, "vehicle.read"),
            "No debe heredar capability de una role de otra company.",
        )

        role_a = Role.objects.create(company=self.company_a, name="Driver")
        RoleCapability.objects.create(role=role_a, capability=cap)
        UserRole.objects.create(user=self.user_a, role=role_a)

        self.assertTrue(user_has_capability(self.user_a, "vehicle.read"))
        self.assertFalse(user_has_capability(self.user_a, "vehicle.manage"))
