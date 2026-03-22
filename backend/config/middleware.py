import uuid

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

from apps.audit.services import reset_current_request, set_current_request
from apps.companies.models import Company


class RequestIDMiddleware:
    """
    Genera y propaga un request_id.
    Esto permite correlacionar logs entre Nginx, Django y workers.

    Si el cliente envía un header X-Request-ID, lo reutilizamos.
    Si no, generamos uno.
    """

    HEADER_NAME = "HTTP_X_REQUEST_ID"  # Django convierte headers a esta forma

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get(self.HEADER_NAME) or str(uuid.uuid4())
        request.request_id = request_id

        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response


class CompanyContextMiddleware:
    """
    Expone company/company_id en el request para evitar lógica repetida.
    Debe ir después de AuthenticationMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.company = None
        request.company_id = None

        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            company_id = getattr(user, "company_id", None)
            if company_id is not None:
                request.company_id = company_id
                # Evita hit extra si user.company ya está hidratado.
                request.company = getattr(user, "company", None)
                if request.company is None:
                    request.company = Company.objects.filter(id=company_id).first()

        return self.get_response(request)


class CompanyRateLimitMiddleware:
    """
    Rate limiting básico por company para endpoints costosos.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.per_minute = int(getattr(settings, "RATE_LIMIT_REPORTS_PER_MIN", 60))
        self.prefixes = ("/api/reports/",)

    def __call__(self, request):
        if request.path.startswith(self.prefixes):
            company_id = getattr(request, "company_id", None)
            if company_id is None and getattr(request, "user", None) is not None and request.user.is_authenticated:
                company_id = getattr(request.user, "company_id", None)
            actor = f"company:{company_id}" if company_id else f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"
            key = f"ratelimit:{actor}:{request.path}"
            current = cache.get(key, 0)
            if current >= self.per_minute:
                return JsonResponse({"detail": "Rate limit exceeded."}, status=429)
            cache.set(key, current + 1, timeout=60)

        return self.get_response(request)


class AuditRequestContextMiddleware:
    """Expone el request actual a la capa de auditoría y limpia el contexto al finalizar."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = set_current_request(request)
        try:
            return self.get_response(request)
        finally:
            reset_current_request(token)
