from django.urls import path

from .views import QuickOnboardingView, SuperadminOverviewView

urlpatterns = [
    path("superadmin/overview/", SuperadminOverviewView.as_view(), name="superadmin-overview"),
    path("superadmin/onboarding/quickstart/", QuickOnboardingView.as_view(), name="superadmin-quickstart"),
]
