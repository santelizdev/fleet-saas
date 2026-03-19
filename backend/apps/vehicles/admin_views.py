"""Vistas custom del admin para la experiencia 360 del vehículo."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView
from unfold.views import UnfoldModelAdminViewMixin

from .models import Vehicle
from .services import build_vehicle_overview


class VehicleOverviewAdminView(UnfoldModelAdminViewMixin, TemplateView):
    """Renderiza la vista estrella 360 consolidando operación por vehículo."""

    title = "Vista 360 del vehículo"
    permission_required = ()
    template_name = "admin/vehicles/vehicle_overview.html"

    def dispatch(self, request, *args, **kwargs):
        queryset = Vehicle.objects.select_related("company", "branch", "assigned_driver")
        if not request.user.is_superuser:
            queryset = queryset.filter(company_id=request.user.company_id)
        self.vehicle = get_object_or_404(queryset, pk=kwargs["object_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(build_vehicle_overview(vehicle=self.vehicle))
        return context
