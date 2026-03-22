from django.urls import path

from .views import health_check, home_landing

urlpatterns = [
    path("", home_landing, name="home"),
    path("health/", health_check, name="health"),
]
