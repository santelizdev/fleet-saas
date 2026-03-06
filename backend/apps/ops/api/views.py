from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alerts.models import JobRun, Notification
from apps.companies.models import Branch, Company
from apps.documents.models import Attachment, VehicleDocument
from apps.product_analytics.models import ProductEvent
from apps.vehicles.models import Vehicle


class SuperadminOnlyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _ensure_superuser(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied("Superadmin only.")


class SuperadminOverviewView(SuperadminOnlyAPIView):
    def get(self, request):
        self._ensure_superuser(request)
        since = timezone.now() - timedelta(hours=24)
        companies = list(
            Company.objects.all()
            .annotate(users_count=Count("users"), vehicles_count=Count("vehicles"))
            .values("id", "name", "rut", "status", "users_count", "vehicles_count")
            .order_by("id")
        )
        failed_notifications = Notification.objects.filter(status=Notification.STATUS_FAILED).count()
        failed_notifications_24h = Notification.objects.filter(status=Notification.STATUS_FAILED, created_at__gte=since).count()
        jobs_24h = list(JobRun.objects.filter(created_at__gte=since).values("job_name", "status", "details", "created_at").order_by("-created_at")[:50])
        storage = list(
            Attachment.objects.values("company_id")
            .annotate(total_bytes=Sum("size_bytes"), files=Count("id"))
            .order_by("company_id")
        )

        activated_companies = 0
        for company in Company.objects.all():
            vehicle_count = Vehicle.objects.filter(company=company).count()
            docs_count = VehicleDocument.objects.filter(company=company).count()
            alerts_events = ProductEvent.objects.filter(company=company, event_name="alert_sent").count()
            if vehicle_count >= 2 and docs_count >= 2 and alerts_events >= 1:
                activated_companies += 1

        return Response(
            {
                "companies": companies,
                "failed_notifications_total": failed_notifications,
                "failed_notifications_24h": failed_notifications_24h,
                "job_runs_24h": jobs_24h,
                "storage_by_company": storage,
                "activation": {
                    "activated_companies": activated_companies,
                    "total_companies": Company.objects.count(),
                },
            }
        )


class QuickOnboardingView(SuperadminOnlyAPIView):
    """
    Onboarding express: empresa + sucursal opcional + vehículos + encargado + conductor.
    """

    def post(self, request):
        self._ensure_superuser(request)
        payload = request.data
        company_name = payload.get("company_name")
        rut = payload.get("rut")
        manager_email = payload.get("manager_email")
        driver_email = payload.get("driver_email")
        vehicles = payload.get("vehicles", [])
        branch_name = payload.get("branch_name")

        if not company_name or not rut or not manager_email or not driver_email:
            return Response(
                {"detail": "company_name, rut, manager_email y driver_email son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        company, _ = Company.objects.get_or_create(rut=rut, defaults={"name": company_name, "status": Company.STATUS_ACTIVE})
        if company.name != company_name:
            company.name = company_name
            company.save(update_fields=["name"])

        branch_id = None
        if branch_name:
            branch, _ = Branch.objects.get_or_create(company=company, name=branch_name)
            branch_id = branch.id

        User = get_user_model()
        manager, _ = User.objects.get_or_create(
            email=manager_email,
            defaults={"name": "Manager", "company": company, "is_staff": True, "is_active": True},
        )
        if manager.company_id != company.id:
            manager.company = company
            manager.save(update_fields=["company"])

        driver, _ = User.objects.get_or_create(
            email=driver_email,
            defaults={"name": "Driver", "company": company, "is_staff": False, "is_active": True},
        )
        if driver.company_id != company.id:
            driver.company = company
            driver.save(update_fields=["company"])

        created_vehicles = []
        for plate in vehicles[:5]:
            vehicle, _ = Vehicle.objects.get_or_create(
                company=company,
                plate=plate,
                defaults={"branch_id": branch_id, "assigned_driver": driver, "status": Vehicle.STATUS_ACTIVE},
            )
            created_vehicles.append(vehicle.id)

        return Response(
            {
                "company_id": company.id,
                "branch_id": branch_id,
                "manager_user_id": manager.id,
                "driver_user_id": driver.id,
                "vehicle_ids": created_vehicles,
            },
            status=status.HTTP_201_CREATED,
        )
