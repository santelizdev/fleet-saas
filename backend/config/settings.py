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
REDIS_CACHE_URL = os.environ.get("REDIS_CACHE_URL") or os.environ.get("REDIS_URL", "")
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    "rest_framework",

    "apps.tags",

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
        "DIRS": [BASE_DIR / "templates"],  # Templates globales para dashboard y vistas operacionales
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
CACHES = (
    {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_CACHE_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
            "KEY_PREFIX": "fleet-saas",
        }
    }
    if REDIS_CACHE_URL
    else {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "fleet-saas-cache",
        }
    }
)
AUTH_USER_MODEL = "accounts.User"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Static files (CSS, JavaScript, Images)
# Necesario para que el admin funcione en desarrollo.
STATIC_URL = "/static/"
MEDIA_URL = "/media/"

# En producción se recomienda recolectar con collectstatic
# y servir con Nginx. Por ahora dejamos rutas estándar.
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"

REPORT_MAX_EXPORT_ROWS = int(os.environ.get("REPORT_MAX_EXPORT_ROWS", "5000"))
REPORT_MAX_EXPORTS_PER_DAY = int(os.environ.get("REPORT_MAX_EXPORTS_PER_DAY", "20"))
RATE_LIMIT_REPORTS_PER_MIN = int(os.environ.get("RATE_LIMIT_REPORTS_PER_MIN", "60"))
ALERT_DEFAULT_MAINTENANCE_REMINDER_DAYS = int(os.environ.get("ALERT_DEFAULT_MAINTENANCE_REMINDER_DAYS", "7"))
ALERT_DEFAULT_MAINTENANCE_REMINDER_KM = int(os.environ.get("ALERT_DEFAULT_MAINTENANCE_REMINDER_KM", "500"))
ALERT_GENERATION_BATCH_SIZE = int(os.environ.get("ALERT_GENERATION_BATCH_SIZE", "500"))
DEFAULT_MAX_VEHICLES = int(os.environ.get("DEFAULT_MAX_VEHICLES", "100"))
DEFAULT_MAX_USERS = int(os.environ.get("DEFAULT_MAX_USERS", "50"))
DEFAULT_MAX_STORAGE_MB = int(os.environ.get("DEFAULT_MAX_STORAGE_MB", "1024"))
DEFAULT_MAX_UPLOADS_PER_DAY = int(os.environ.get("DEFAULT_MAX_UPLOADS_PER_DAY", "200"))
DEFAULT_MAX_EXPORTS_PER_DAY = int(os.environ.get("DEFAULT_MAX_EXPORTS_PER_DAY", "20"))
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@fleet.local")
EMAIL_BACKEND = os.environ.get("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("DJANGO_EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("DJANGO_EMAIL_USE_TLS", "0") == "1"
EMAIL_USE_SSL = os.environ.get("DJANGO_EMAIL_USE_SSL", "0") == "1"
NOTIFICATION_PUSH_BACKEND = os.environ.get("NOTIFICATION_PUSH_BACKEND", "console")
NOTIFICATION_PUSH_WEBHOOK_URL = os.environ.get("NOTIFICATION_PUSH_WEBHOOK_URL", "")
NOTIFICATION_PUSH_WEBHOOK_TOKEN = os.environ.get("NOTIFICATION_PUSH_WEBHOOK_TOKEN", "")
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@fleet.local")
SUPPORT_WHATSAPP = os.environ.get("SUPPORT_WHATSAPP", "+56 9 0000 0000")

USE_HTTPS_HEADERS = os.environ.get("DJANGO_USE_HTTPS_HEADERS", "0") == "1"
if USE_HTTPS_HEADERS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True



# Configuración visual y navegación del admin moderno.
UNFOLD = {
    "SITE_TITLE": "RutaCore Admin",
    "SITE_HEADER": "RutaCore",
    "SITE_SUBHEADER": "Operación, analítica y control de flota",
    "SITE_SYMBOL": "directions_car",
    "SITE_LOGO": "/static/admin/branding/rutacore-logo.svg",
    "SITE_ICON": "/static/admin/branding/rutacore-icon.svg",
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "href": "/static/admin/branding/rutacore-icon.svg",
            "type": "image/svg+xml",
        }
    ],
    "COLORS": {
        "base": {
            "50": "#F6F8FB",
            "100": "#ECF1F8",
            "200": "#D8E0EC",
            "300": "#B6C2D6",
            "400": "#8092B3",
            "500": "#526481",
            "600": "#3B4D74",
            "700": "#2C3D63",
            "800": "#1D2E53",
            "900": "#162544",
            "950": "#0D1730",
        },
        "primary": {
            "50": "#FFF7ED",
            "100": "#FFEDD5",
            "200": "#FED7AA",
            "300": "#FDBA74",
            "400": "#FB923C",
            "500": "#F97316",
            "600": "#EA580C",
            "700": "#C2410C",
            "800": "#9A3412",
            "900": "#7C2D12",
            "950": "#431407",
        },
    },
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "DASHBOARD_CALLBACK": "apps.ops.admin_dashboard.dashboard_callback",
    "ENVIRONMENT": "config.unfold.environment_callback",
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": "config.unfold.navigation",
    },
    "STYLES": [
        "/static/admin/css/operations_dashboard.css",
    ],
}
