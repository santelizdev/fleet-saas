import csv
import io

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasCapability
from apps.companies.limits import enforce_vehicle_limit
from apps.product_analytics.events import track_event
from apps.vehicles.models import Vehicle

from .serializers import VehicleCSVImportSerializer, VehicleSerializer


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all().order_by("-id")
    serializer_class = VehicleSerializer
    capability_by_action = {
        "list": "vehicle.read",
        "retrieve": "vehicle.read",
        "create": "vehicle.manage",
        "update": "vehicle.manage",
        "partial_update": "vehicle.manage",
        "destroy": "vehicle.manage",
        "import_csv": "vehicle.manage",
    }

    def get_permissions(self):
        self.required_capability = self.capability_by_action.get(self.action, "vehicle.read")
        return [IsAuthenticated(), HasCapability()]

    def _request_company_id(self):
        company_id = getattr(self.request, "company_id", None)
        if company_id is None and getattr(self.request.user, "is_authenticated", False):
            company_id = getattr(self.request.user, "company_id", None)
        return company_id

    def get_queryset(self):
        return super().get_queryset().filter(company_id=self._request_company_id())

    def perform_create(self, serializer):
        company_id = self._request_company_id()
        enforce_vehicle_limit(company_id=company_id, actor_id=self.request.user.id, new_units=1)
        obj = serializer.save(company_id=company_id)
        track_event(
            company_id=company_id,
            actor_id=self.request.user.id,
            event_name="vehicle_created",
            payload={"vehicle_id": obj.id, "plate": obj.plate},
        )

    @action(methods=["post"], detail=False, url_path="import-csv")
    def import_csv(self, request):
        serializer = VehicleCSVImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        csv_content = serializer.validated_data["csv_content"].replace("\\n", "\n")
        reader = csv.DictReader(io.StringIO(csv_content))
        required_cols = {"plate"}
        if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
            raise ValidationError("CSV debe incluir al menos la columna 'plate'.")

        rows = [row for row in reader if (row.get("plate") or "").strip()]
        if not rows:
            raise ValidationError("CSV no contiene filas válidas con plate.")

        company_id = self._request_company_id()
        enforce_vehicle_limit(company_id=company_id, actor_id=request.user.id, new_units=len(rows))

        created = 0
        existing = 0
        created_ids = []
        for row in rows:
            plate = row.get("plate", "").strip()
            vehicle, was_created = Vehicle.objects.get_or_create(
                company_id=company_id,
                plate=plate,
                defaults={
                    "brand": (row.get("brand") or "").strip(),
                    "model": (row.get("model") or "").strip(),
                    "year": int(row["year"]) if (row.get("year") or "").strip() else None,
                    "status": row.get("status") or Vehicle.STATUS_ACTIVE,
                    "current_km": int(row["current_km"]) if (row.get("current_km") or "").strip() else 0,
                },
            )
            if was_created:
                created += 1
                created_ids.append(vehicle.id)
                track_event(
                    company_id=company_id,
                    actor_id=request.user.id,
                    event_name="vehicle_created",
                    payload={"vehicle_id": vehicle.id, "plate": vehicle.plate, "source": "csv"},
                )
            else:
                existing += 1

        return Response(
            {
                "created": created,
                "existing": existing,
                "created_ids": created_ids,
            },
            status=status.HTTP_201_CREATED,
        )
