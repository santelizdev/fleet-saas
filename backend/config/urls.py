from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("apps.health.urls")),
    path("api/vehicles/", include("apps.vehicles.api.urls")),
    path("api/expenses/", include("apps.expenses.api.urls")),
    path("api/documents/", include("apps.documents.api.urls")),
    path("api/alerts/", include("apps.alerts.api.urls")),
    path("api/reports/", include("apps.reports.api.urls")),
    path("api/internal/", include("apps.ops.api.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
