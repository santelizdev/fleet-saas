from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ProductAnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.product_analytics"
    verbose_name = _("Analítica de producto")
