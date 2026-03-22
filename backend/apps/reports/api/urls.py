from django.urls import path

from .views import DashboardReportView, ExportOperationalSummaryPDFView, ExportVehicleCostCSVView, VehicleCostReportView

urlpatterns = [
    path("dashboard/", DashboardReportView.as_view(), name="report-dashboard"),
    path("vehicle-costs/", VehicleCostReportView.as_view(), name="report-vehicle-costs"),
    path("vehicle-costs/export.csv", ExportVehicleCostCSVView.as_view(), name="report-vehicle-costs-export"),
    path("overview/export.pdf", ExportOperationalSummaryPDFView.as_view(), name="report-overview-export-pdf"),
]
