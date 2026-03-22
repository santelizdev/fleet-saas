"""Formularios públicos mínimos para captación comercial del home."""

from django import forms


class QuoteRequestForm(forms.Form):
    """Formulario de cotización liviano para prospectos SaaS."""

    full_name = forms.CharField(label="Nombre", max_length=120)
    company_name = forms.CharField(label="Empresa", max_length=120)
    email = forms.EmailField(label="Email corporativo")
    phone = forms.CharField(label="Teléfono", max_length=40)
    fleet_size = forms.IntegerField(label="Vehículos", min_value=1, max_value=10000)
    message = forms.CharField(
        label="Cuéntanos tu operación",
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
    )
