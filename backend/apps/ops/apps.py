from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class OpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ops"
    verbose_name = _("Operaciones")
