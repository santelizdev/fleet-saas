from django import forms

from .models import DriverLicense, VehicleDocument
from .services import validate_support_image


class VehicleDocumentAdminForm(forms.ModelForm):
    support_image = forms.ImageField(required=False)

    class Meta:
        model = VehicleDocument
        fields = "__all__"

    def clean_support_image(self):
        support_image = self.cleaned_data.get("support_image")
        if support_image:
            validate_support_image(support_image)
        return support_image


class DriverLicenseAdminForm(forms.ModelForm):
    support_image = forms.ImageField(required=False)

    class Meta:
        model = DriverLicense
        fields = "__all__"

    def clean_support_image(self):
        support_image = self.cleaned_data.get("support_image")
        if support_image:
            validate_support_image(support_image)
        return support_image
