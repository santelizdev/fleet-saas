from django import forms
from django.http import JsonResponse
from django.db import models
from django.urls import path, reverse

from apps.accounts.models import UserRole
from apps.companies.models import Company


class CompanyScopedAdminMixin:
    """
    Restringe queryset/admin form choices a la company del usuario autenticado.
    Además usa inputs de fecha nativos para facilitar cambio de año.
    """

    company_filter_lookup = "company_id"
    form_company_filters = {}
    list_before_template = "admin/_company_scope_toolbar.html"
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
        scoped_company_id = getattr(request, "_company_scope_value", None)
        if scoped_company_id is not None:
            return scoped_company_id

        company_id = self._current_company_id(request)
        if company_id is not None:
            return company_id

        for key in ("company_scope", "company", "company_id"):
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

    def _available_companies(self, request):
        if not request.user.is_superuser:
            return Company.objects.filter(id=getattr(request.user, "company_id", None))
        return Company.objects.all().order_by("name")

    def _company_scope_value(self, request):
        scoped_company_id = getattr(request, "_company_scope_value", None)
        if scoped_company_id is not None:
            return scoped_company_id

        if not request.user.is_superuser:
            return getattr(request.user, "company_id", None)
        value = request.GET.get("company_scope") or request.POST.get("company_scope")
        if not value:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _company_scope_context(self, request):
        preserved_filters = []
        for key, values in request.GET.lists():
            if key in {"company_scope", "p"}:
                continue
            for value in values:
                preserved_filters.append({"key": key, "value": value})

        return {
            "company_scope_enabled": request.user.is_superuser,
            "company_scope_value": self._company_scope_value(request),
            "company_scope_companies": list(self._available_companies(request)),
            "company_scope_preserved_filters": preserved_filters,
        }

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
        company_id = self._selected_company_id(request)
        if company_id is not None:
            qs = qs.filter(**{self.company_filter_lookup: company_id})
        if self._is_pilot_user(request):
            qs = self._filter_queryset_for_pilot(request, qs)
        return qs

    def lookup_allowed(self, lookup, value, request=None):
        """
        Permite usar company_scope como query param auxiliar del changelist.

        Django Admin redirige a ?e=1 cuando encuentra parámetros GET que no
        reconoce como filtros válidos. Sin este whitelist el selector de
        empresa parece un error de base de datos aunque la DB esté sana.
        """

        if lookup == "company_scope":
            return True
        return super().lookup_allowed(lookup, value, request=request)

    def changelist_view(self, request, extra_context=None):
        if request.user.is_superuser and "company_scope" in request.GET:
            request._company_scope_value = self._selected_company_id(request)
            mutable_get = request.GET.copy()
            mutable_get.pop("company_scope", None)
            request.GET = mutable_get

        extra_context = extra_context or {}
        extra_context.update(self._company_scope_context(request))
        return super().changelist_view(request, extra_context=extra_context)

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
