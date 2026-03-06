from __future__ import annotations

from typing import Any

from apps.companies.models import Company


def get_company(request: Any, required: bool = False) -> Company | None:
    """
    Retorna la empresa activa del request.

    Prioridad:
    1) request.company (seteado por middleware)
    2) request.user.company (si existe y está autenticado)
    """

    company = getattr(request, "company", None)
    if company is None:
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            company = getattr(user, "company", None)

    if required and company is None:
        raise Company.DoesNotExist("No hay company en el contexto del request.")

    return company


def get_company_id(request: Any) -> int | None:
    company = get_company(request, required=False)
    if company is None:
        return None
    return company.id
