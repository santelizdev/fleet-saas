from rest_framework import serializers

from apps.expenses.models import ExpenseCategory, VehicleExpense, VehicleExpenseAttachment


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "company", "name", "description", "created_at"]
        read_only_fields = ["id", "company", "created_at"]


class VehicleExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleExpense
        fields = [
            "id",
            "company",
            "vehicle",
            "category",
            "amount_clp",
            "expense_date",
            "supplier",
            "km",
            "invoice_number",
            "notes",
            "approval_status",
            "payment_status",
            "reported_by",
            "approved_by",
            "paid_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "company",
            "approval_status",
            "payment_status",
            "reported_by",
            "approved_by",
            "paid_by",
            "created_at",
            "updated_at",
        ]


class VehicleExpenseAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleExpenseAttachment
        fields = ["id", "company", "vehicle_expense", "attachment", "created_at"]
        read_only_fields = ["id", "company", "created_at"]
