from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.utils.translation import gettext_lazy as _

from .models import User


UNFOLD_TEXT_INPUT_CSS = (
    "border border-base-200 bg-white font-medium min-w-20 placeholder-base-400 "
    "rounded-default shadow-xs text-font-default-light text-sm focus:outline-2 "
    "focus:-outline-offset-2 focus:outline-primary-600 group-[.errors]:border-red-600 "
    "focus:group-[.errors]:outline-red-600 dark:bg-base-900 dark:border-base-700 "
    "dark:text-font-default-dark dark:group-[.errors]:border-red-500 "
    "dark:focus:group-[.errors]:outline-red-500 dark:scheme-dark "
    "group-[.primary]:border-transparent px-3 py-2 w-full max-w-2xl "
)


class UserAdminCreationForm(forms.ModelForm):
    password1 = forms.CharField(
        label=_("Contraseña"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": UNFOLD_TEXT_INPUT_CSS,
                "autocomplete": "new-password",
            }
        ),
    )
    password2 = forms.CharField(
        label=_("Confirmación de contraseña"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": UNFOLD_TEXT_INPUT_CSS,
                "autocomplete": "new-password",
            }
        ),
    )

    class Meta:
        model = User
        fields = ("email", "name", "phone", "company", "is_active", "is_staff")
        labels = {
            "email": _("Correo"),
            "name": _("Nombre"),
            "phone": _("Teléfono"),
            "company": _("Empresa"),
            "is_active": _("Activo"),
            "is_staff": _("Acceso al admin"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("password1", "password2"):
            widget = self.fields[field_name].widget
            widget.attrs["class"] = widget.attrs.get("class") or UNFOLD_TEXT_INPUT_CSS
            widget.attrs.setdefault("autocomplete", "new-password")

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
        label=_("Contraseña"),
        help_text=_("Las contraseñas no se almacenan en texto plano. Usa el formulario de cambio para actualizarla."),
    )

    class Meta:
        model = User
        fields = ("email", "password", "name", "phone", "company", "is_active", "is_staff", "is_superuser")
        labels = {
            "email": _("Correo"),
            "name": _("Nombre"),
            "phone": _("Teléfono"),
            "company": _("Empresa"),
            "is_active": _("Activo"),
            "is_staff": _("Acceso al admin"),
            "is_superuser": _("Superusuario"),
        }

    def clean_password(self):
        return self.initial.get("password")
