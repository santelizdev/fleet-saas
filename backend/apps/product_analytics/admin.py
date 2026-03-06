from django.contrib import admin

from config.admin_scoping import CompanyScopedAdminMixin

from .models import ProductEvent


@admin.register(ProductEvent)
class ProductEventAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "company", "event_name", "actor", "created_at")
    list_filter = ("company", "event_name")
    search_fields = ("event_name", "actor__email")
