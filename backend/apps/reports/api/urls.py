from django.urls import path

from .views import DashboardReportView, ExportVehicleCostCSVView, VehicleCostReportView

urlpatterns = [
    path("dashboard/", DashboardReportView.as_view(), name="report-dashboard"),
    path("vehicle-costs/", VehicleCostReportView.as_view(), name="report-vehicle-costs"),
    path("vehicle-costs/export.csv", ExportVehicleCostCSVView.as_view(), name="report-vehicle-costs-export"),
]
