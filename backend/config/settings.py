import os
import dj_database_url
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
CSRF_TRUSTED_ORIGINS = [v for v in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if v]

DATABASES = {
  "default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=60),
}
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",

    "apps.companies",
    "apps.accounts",
    "apps.vehicles",
    "apps.audit",
    "apps.health",
    "apps.documents",
    "apps.alerts",
    "apps.maintenance",
    "apps.reports",
    "apps.product_analytics",
    "apps.ops",
    "apps.expenses",
]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],  # Luego puedes agregar BASE_DIR / "templates" si usas templates propios
        "APP_DIRS": True,  # Necesario para que Django encuentre templates dentro de las apps (incluye admin)
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",  # Requerido por el admin
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "config.middleware.CompanyContextMiddleware",
    "config.middleware.CompanyRateLimitMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # Debe ir al final o cerca del final para que envuelva todo.
    "config.middleware.RequestIDMiddleware",
]
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "fleet-saas-cache",
    }
}
AUTH_USER_MODEL = "accounts.User"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Static files (CSS, JavaScript, Images)
# Necesario para que el admin funcione en desarrollo.
STATIC_URL = "/static/"
MEDIA_URL = "/media/"

# En producción se recomienda recolectar con collectstatic
# y servir con Nginx. Por ahora dejamos rutas estándar.
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"

REPORT_MAX_EXPORT_ROWS = int(os.environ.get("REPORT_MAX_EXPORT_ROWS", "5000"))
REPORT_MAX_EXPORTS_PER_DAY = int(os.environ.get("REPORT_MAX_EXPORTS_PER_DAY", "20"))
RATE_LIMIT_REPORTS_PER_MIN = int(os.environ.get("RATE_LIMIT_REPORTS_PER_MIN", "60"))
DEFAULT_MAX_VEHICLES = int(os.environ.get("DEFAULT_MAX_VEHICLES", "100"))
DEFAULT_MAX_USERS = int(os.environ.get("DEFAULT_MAX_USERS", "50"))
DEFAULT_MAX_STORAGE_MB = int(os.environ.get("DEFAULT_MAX_STORAGE_MB", "1024"))
DEFAULT_MAX_UPLOADS_PER_DAY = int(os.environ.get("DEFAULT_MAX_UPLOADS_PER_DAY", "200"))
DEFAULT_MAX_EXPORTS_PER_DAY = int(os.environ.get("DEFAULT_MAX_EXPORTS_PER_DAY", "20"))
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@fleet.local")
SUPPORT_WHATSAPP = os.environ.get("SUPPORT_WHATSAPP", "+56 9 0000 0000")

USE_HTTPS_HEADERS = os.environ.get("DJANGO_USE_HTTPS_HEADERS", "0") == "1"
if USE_HTTPS_HEADERS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
