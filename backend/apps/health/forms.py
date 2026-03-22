"""Formularios públicos mínimos para captación comercial del home."""

from django import forms
from django.utils.translation import gettext_lazy as _


class QuoteRequestForm(forms.Form):
    """Formulario de cotización liviano para prospectos SaaS."""

    full_name = forms.CharField(label=_("Nombre"), max_length=120)
    company_name = forms.CharField(label=_("Empresa"), max_length=120)
    email = forms.EmailField(label=_("Email corporativo"))
    phone = forms.CharField(label=_("Teléfono"), max_length=40)
    fleet_size = forms.IntegerField(label=_("Vehículos"), min_value=1, max_value=10000)
    message = forms.CharField(
        label=_("Cuéntanos tu operación"),
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
    )
