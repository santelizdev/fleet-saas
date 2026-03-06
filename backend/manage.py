#!/usr/bin/env python
"""
Django's command-line utility for administrative tasks.

Este archivo es el entrypoint estándar de Django.
Si está vacío o dañado, comandos como migrate/shell/runserver no harán nada.
"""
import os
import sys


def main() -> None:
    """
    Ejecuta la CLI de Django.

    - Define DJANGO_SETTINGS_MODULE para que Django sepa qué settings cargar.
    - Llama a execute_from_command_line para procesar comandos: migrate, shell, runserver, etc.
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "No se pudo importar Django. ¿Instalaste requirements.txt? "
            "¿Estás ejecutando el comando dentro del contenedor correcto?"
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()