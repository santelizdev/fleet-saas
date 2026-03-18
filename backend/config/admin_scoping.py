from django import forms
from django.http import JsonResponse
from django.db import models
from django.urls import path, reverse

from apps.accounts.models import UserRole


class CompanyScopedAdminMixin:
    """
    Restringe queryset/admin form choices a la company del usuario autenticado.
    Además usa inputs de fecha nativos para facilitar cambio de año.
    """

    company_filter_lookup = "company_id"
    form_company_filters = {}
    formfield_overrides = {
        models.DateField: {"widget": forms.DateInput(attrs={"type": "date"})},
    }

    class Media:
        js = ("admin/js/company_dependent_selects.js",)

    def _current_company_id(self, request):
        if request.user.is_superuser:
            return None
        return getattr(request.user, "company_id", None)

    def _is_pilot_user(self, request):
        if request.user.is_superuser:
            return False
        return UserRole.objects.filter(
            user=request.user,
            role__name__iregex=r"^(driver|piloto)$",
        ).exists()

    def _selected_company_id(self, request):
        company_id = self._current_company_id(request)
        if company_id is not None:
            return company_id

        for key in ("company", "company_id"):
            value = request.POST.get(key) or request.GET.get(key)
            if value:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None

        object_id = getattr(getattr(request, "resolver_match", None), "kwargs", {}).get("object_id")
        if object_id:
            obj = self.get_object(request, object_id)
            if obj is not None:
                return getattr(obj, "company_id", None)
        return None

    def _dynamic_company_fields(self):
        return tuple(name for name in self.form_company_filters.keys() if name != "company")

    def _company_options_url_name(self):
        opts = self.model._meta
        return f"admin:{opts.app_label}_{opts.model_name}_company_options"

    def _filter_related_queryset(self, db_field, request, queryset):
        if db_field.name in {"driver", "assigned_driver"}:
            queryset = queryset.filter(is_superuser=False, is_active=True).distinct()

        if not self._is_pilot_user(request):
            return queryset

        if db_field.name == "vehicle":
            return queryset.filter(assigned_driver=request.user)
        if db_field.name == "vehicle_document":
            return queryset.filter(vehicle__assigned_driver=request.user)
        if db_field.name == "driver_license":
            return queryset.filter(driver=request.user)
        if db_field.name == "driver":
            return queryset.filter(id=request.user.id)
        return queryset

    def _filter_queryset_for_pilot(self, request, qs):
        model_name = qs.model._meta.model_name
        if model_name == "vehicle":
            return qs.filter(assigned_driver=request.user)
        if model_name == "vehicledocument":
            return qs.filter(vehicle__assigned_driver=request.user)
        if model_name == "vehicledocumentattachment":
            return qs.filter(vehicle_document__vehicle__assigned_driver=request.user)
        if model_name == "driverlicense":
            return qs.filter(driver=request.user)
        if model_name == "driverlicenseattachment":
            return qs.filter(driver_license__driver=request.user)
        if model_name == "documentalert":
            return qs.filter(
                models.Q(vehicle_document__vehicle__assigned_driver=request.user)
                | models.Q(driver_license__driver=request.user)
            )
        if model_name == "vehicleexpense":
            return qs.filter(vehicle__assigned_driver=request.user)
        if model_name == "vehicleexpenseattachment":
            return qs.filter(vehicle_expense__vehicle__assigned_driver=request.user)
        return qs

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        company_id = self._current_company_id(request)
        if company_id is not None:
            qs = qs.filter(**{self.company_filter_lookup: company_id})
        if self._is_pilot_user(request):
            qs = self._filter_queryset_for_pilot(request, qs)
        return qs

    def get_urls(self):
        opts = self.model._meta
        custom_urls = [
            path(
                "company-options/",
                self.admin_site.admin_view(self.company_options_view),
                name=f"{opts.app_label}_{opts.model_name}_company_options",
            )
        ]
        return custom_urls + super().get_urls()

    def company_options_view(self, request):
        field_name = request.GET.get("field")
        if field_name not in self._dynamic_company_fields():
            return JsonResponse({"options": []}, status=400)

        company_id = self._selected_company_id(request)
        if company_id is None:
            return JsonResponse({"options": []})

        db_field = self.model._meta.get_field(field_name)
        lookup = self.form_company_filters[field_name]
        queryset = db_field.related_model.objects.filter(**{lookup: company_id})
        queryset = self._filter_related_queryset(db_field, request, queryset)
        options = [{"value": str(obj.pk), "label": str(obj)} for obj in queryset.order_by("pk")[:200]]
        return JsonResponse({"options": options})

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        lookup = self.form_company_filters.get(db_field.name)
        if lookup:
            company_id = self._selected_company_id(request)
            if db_field.name == "company":
                current_company_id = self._current_company_id(request)
                if current_company_id is not None:
                    queryset = db_field.related_model.objects.filter(id=current_company_id)
                else:
                    queryset = db_field.related_model.objects.all()
            elif company_id is not None:
                queryset = db_field.related_model.objects.filter(**{lookup: company_id})
                queryset = self._filter_related_queryset(db_field, request, queryset)
            else:
                queryset = db_field.related_model.objects.none()
            kwargs["queryset"] = queryset

        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name in self._dynamic_company_fields():
            formfield.widget.attrs["data-company-dependent"] = "1"
            formfield.widget.attrs["data-field-name"] = db_field.name
            formfield.widget.attrs["data-options-url"] = reverse(self._company_options_url_name())
        return formfield
