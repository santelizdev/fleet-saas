"""Configuración de la app TAG / pórticos."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class TagsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tags"
    verbose_name = _("TAG / Pórticos")
