class CompanyScopedAdminMixin:
    """
    Restringe queryset/admin form choices a la company del usuario autenticado.
    """

    company_filter_lookup = "company_id"
    form_company_filters = {}

    def _current_company_id(self, request):
        if request.user.is_superuser:
            return None
        return getattr(request.user, "company_id", None)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        company_id = self._current_company_id(request)
        if company_id is None:
            return qs
        return qs.filter(**{self.company_filter_lookup: company_id})

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        company_id = self._current_company_id(request)
        if company_id is not None:
            lookup = self.form_company_filters.get(db_field.name)
            if lookup:
                kwargs["queryset"] = db_field.related_model.objects.filter(**{lookup: company_id})
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
