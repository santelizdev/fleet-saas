from django import forms

from apps.documents.services import validate_support_image

from .models import VehicleExpense


class VehicleExpenseAdminForm(forms.ModelForm):
    support_image = forms.ImageField(required=False)

    class Meta:
        model = VehicleExpense
        fields = "__all__"

    def clean_support_image(self):
        support_image = self.cleaned_data.get("support_image")
        if support_image:
            validate_support_image(support_image)
        return support_image
