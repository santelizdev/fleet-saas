from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.companies.models import Company
from apps.documents.models import Attachment
from apps.vehicles.models import Vehicle


class ExpenseCategory(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="expense_categories")
    name = models.CharField(max_length=64)
    description = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="uniq_expense_category_company_name"),
        ]
        indexes = [models.Index(fields=["company", "name"])]

    def __str__(self):
        return f"{self.company_id}:{self.name}"


class VehicleExpense(models.Model):
    APPROVAL_REPORTED = "reported"
    APPROVAL_APPROVED = "approved"
    APPROVAL_REJECTED = "rejected"
    APPROVAL_CHOICES = [
        (APPROVAL_REPORTED, "Reported"),
        (APPROVAL_APPROVED, "Approved"),
        (APPROVAL_REJECTED, "Rejected"),
    ]

    PAYMENT_UNPAID = "unpaid"
    PAYMENT_PAID = "paid"
    PAYMENT_CHOICES = [
        (PAYMENT_UNPAID, "Unpaid"),
        (PAYMENT_PAID, "Paid"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="vehicle_expenses")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="expenses")
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses")
    amount_clp = models.PositiveIntegerField()
    expense_date = models.DateField()
    supplier = models.CharField(max_length=255, blank=True, default="")
    km = models.PositiveIntegerField(default=0)
    invoice_number = models.CharField(max_length=64, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    approval_status = models.CharField(max_length=16, choices=APPROVAL_CHOICES, default=APPROVAL_REPORTED)
    payment_status = models.CharField(max_length=16, choices=PAYMENT_CHOICES, default=PAYMENT_UNPAID)

    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reported_expenses")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_expenses")
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="paid_expenses")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Gasto de vehículo"
        verbose_name_plural = "Gastos de vehículo"
        indexes = [
            models.Index(fields=["company", "vehicle", "expense_date"]),
            models.Index(fields=["company", "approval_status", "payment_status"]),
        ]

    def clean(self):
        if self.vehicle_id and self.company_id and self.vehicle.company_id != self.company_id:
            raise ValidationError("Vehicle y Expense deben pertenecer a la misma company.")
        if self.category_id and self.company_id and self.category.company_id != self.company_id:
            raise ValidationError("Category y Expense deben pertenecer a la misma company.")
        if self.reported_by_id and self.company_id and self.reported_by.company_id != self.company_id:
            raise ValidationError("reported_by debe pertenecer a la misma company.")
        if self.approved_by_id and self.company_id and self.approved_by.company_id != self.company_id:
            raise ValidationError("approved_by debe pertenecer a la misma company.")
        if self.paid_by_id and self.company_id and self.paid_by.company_id != self.company_id:
            raise ValidationError("paid_by debe pertenecer a la misma company.")
        if self.payment_status == self.PAYMENT_PAID and self.approval_status != self.APPROVAL_APPROVED:
            raise ValidationError("Solo se puede pagar un gasto aprobado.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def support_attachment(self) -> Attachment | None:
        link = self.attachment_links.select_related("attachment").order_by("-id").first()
        return link.attachment if link else None


class VehicleExpenseAttachment(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="vehicle_expense_attachments")
    vehicle_expense = models.ForeignKey(VehicleExpense, on_delete=models.CASCADE, related_name="attachment_links")
    attachment = models.ForeignKey(Attachment, on_delete=models.CASCADE, related_name="expense_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["vehicle_expense", "attachment"], name="uniq_vehicle_expense_attachment"),
        ]
        indexes = [models.Index(fields=["company", "vehicle_expense"])]

    def clean(self):
        if self.vehicle_expense_id and self.company_id and self.vehicle_expense.company_id != self.company_id:
            raise ValidationError("Expense y link deben pertenecer a la misma company.")
        if self.attachment_id and self.company_id and self.attachment.company_id != self.company_id:
            raise ValidationError("Attachment y link deben pertenecer a la misma company.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
