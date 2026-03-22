"""Formularios operativos del módulo TAG."""

from __future__ import annotations

from django import forms

from apps.companies.models import Company
from apps.vehicles.models import Vehicle


class TagCsvImportForm(forms.Form):
    """Carga manual de cartolas CSV entregadas por concesionarias/autopistas."""

    source_name = forms.CharField(
        label="Origen del archivo",
        max_length=120,
        initial="Carga manual CSV",
    )
    company = forms.ModelChoiceField(
        label="Empresa",
        queryset=Company.objects.none(),
        required=False,
    )
    vehicle = forms.ModelChoiceField(
        label="Vehículo objetivo",
        queryset=Vehicle.objects.none(),
        help_text="La patente del CSV debe coincidir con este vehículo para evitar cargas cruzadas.",
    )
    csv_file = forms.FileField(
        label="Archivo CSV de autopista",
        help_text="Usa el archivo detalle con columnas Patente, FechaHora, Portico, Concesionaria, TAG, Horario, Importe y Factura.",
    )

    def __init__(
        self,
        *args,
        companies=None,
        vehicles=None,
        show_company=True,
        selected_company=None,
        selected_vehicle=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.fields["company"].queryset = companies if companies is not None else Company.objects.none()
        self.fields["vehicle"].queryset = vehicles if vehicles is not None else Vehicle.objects.none()
        self.fields["company"].empty_label = "Selecciona una empresa"
        self.fields["vehicle"].empty_label = "Selecciona un vehículo"
        if not self.is_bound:
            if selected_company is not None:
                self.fields["company"].initial = selected_company
            if selected_vehicle is not None:
                self.fields["vehicle"].initial = selected_vehicle
        if not show_company:
            self.fields.pop("company", None)

    def clean(self):
        cleaned_data = super().clean()
        company = cleaned_data.get("company")
        vehicle = cleaned_data.get("vehicle")
        if company and vehicle and vehicle.company_id != company.id:
            self.add_error("vehicle", "El vehículo seleccionado no pertenece a la empresa elegida.")
        return cleaned_data
