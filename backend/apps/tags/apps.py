"""Configuración de la app TAG / pórticos."""

from django.apps import AppConfig


class TagsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tags"
    verbose_name = "TAG / Pórticos"
