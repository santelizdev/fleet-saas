from django.db import transaction
from rest_framework import serializers

from apps.documents.api.serializers import AttachmentSerializer
from apps.documents.services import replace_vehicle_expense_attachment, validate_support_image
from apps.expenses.models import ExpenseCategory, VehicleExpense, VehicleExpenseAttachment


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "company", "name", "description", "created_at"]
        read_only_fields = ["id", "company", "created_at"]


class VehicleExpenseSerializer(serializers.ModelSerializer):
    support_image = serializers.ImageField(write_only=True, required=False, allow_null=True)
    support_attachment = AttachmentSerializer(read_only=True)

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
            "support_attachment",
            "support_image",
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

    def validate_support_image(self, value):
        try:
            validate_support_image(value)
        except Exception as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value

    def create(self, validated_data):
        support_image = validated_data.pop("support_image", None)
        with transaction.atomic():
            instance = super().create(validated_data)
            if support_image:
                request = self.context.get("request")
                replace_vehicle_expense_attachment(
                    expense=instance,
                    uploaded_file=support_image,
                    actor_id=request.user.id if request else None,
                )
            return instance

    def update(self, instance, validated_data):
        support_image = validated_data.pop("support_image", None)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            if support_image:
                request = self.context.get("request")
                replace_vehicle_expense_attachment(
                    expense=instance,
                    uploaded_file=support_image,
                    actor_id=request.user.id if request else None,
                )
            return instance


class VehicleExpenseAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleExpenseAttachment
        fields = ["id", "company", "vehicle_expense", "attachment", "created_at"]
        read_only_fields = ["id", "company", "created_at"]
