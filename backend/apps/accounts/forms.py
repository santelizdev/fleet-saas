from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField

from .models import User


class UserAdminCreationForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label="Password confirmation", strip=False, widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("email", "name", "phone", "company", "is_active", "is_staff")

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserAdminChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(
        label="Password",
        help_text="Las contraseñas no se almacenan en texto plano. Usa el formulario de cambio para actualizarla.",
    )

    class Meta:
        model = User
        fields = ("email", "password", "name", "phone", "company", "is_active", "is_staff", "is_superuser")

    def clean_password(self):
        return self.initial.get("password")
