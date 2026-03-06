from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasCapability
from apps.audit.models import AuditLog
from apps.companies.limits import enforce_upload_limits
from apps.expenses.models import ExpenseCategory, VehicleExpense, VehicleExpenseAttachment
from apps.product_analytics.events import track_event

from .serializers import ExpenseCategorySerializer, VehicleExpenseAttachmentSerializer, VehicleExpenseSerializer


class ExpenseCapabilityViewSet(viewsets.ModelViewSet):
    capability_by_action = {
        "list": "expense.read",
        "retrieve": "expense.read",
        "create": "expense.report",
        "update": "expense.report",
        "partial_update": "expense.report",
        "destroy": "expense.report",
        "approve": "expense.approve",
        "reject": "expense.approve",
        "pay": "expense.pay",
    }

    def get_permissions(self):
        self.required_capability = self.capability_by_action.get(self.action, "expense.read")
        return [IsAuthenticated(), HasCapability()]

    def _request_company_id(self):
        company_id = getattr(self.request, "company_id", None)
        if company_id is None and getattr(self.request.user, "is_authenticated", False):
            company_id = getattr(self.request.user, "company_id", None)
        return company_id


class ExpenseCategoryViewSet(ExpenseCapabilityViewSet):
    queryset = ExpenseCategory.objects.all().order_by("name")
    serializer_class = ExpenseCategorySerializer

    def get_queryset(self):
        return super().get_queryset().filter(company_id=self._request_company_id())

    def perform_create(self, serializer):
        serializer.save(company_id=self._request_company_id())


class VehicleExpenseViewSet(ExpenseCapabilityViewSet):
    queryset = VehicleExpense.objects.select_related("vehicle", "category").all().order_by("-id")
    serializer_class = VehicleExpenseSerializer

    def get_queryset(self):
        return super().get_queryset().filter(company_id=self._request_company_id())

    def perform_create(self, serializer):
        company_id = self._request_company_id()
        expense = serializer.save(company_id=company_id, reported_by=self.request.user)
        AuditLog.objects.create(
            company_id=company_id,
            actor_id=self.request.user.id,
            action="expense.report",
            object_type="VehicleExpense",
            object_id=str(expense.id),
            after_json={"amount_clp": expense.amount_clp, "vehicle_id": expense.vehicle_id},
        )
        track_event(
            company_id=company_id,
            actor_id=self.request.user.id,
            event_name="expense_reported",
            payload={"expense_id": expense.id, "amount_clp": expense.amount_clp},
        )

    @action(methods=["post"], detail=True)
    def approve(self, request, pk=None):
        expense = self.get_object()
        expense.approval_status = VehicleExpense.APPROVAL_APPROVED
        expense.approved_by = request.user
        expense.save(update_fields=["approval_status", "approved_by", "updated_at"])
        AuditLog.objects.create(
            company_id=expense.company_id,
            actor_id=request.user.id,
            action="expense.approve",
            object_type="VehicleExpense",
            object_id=str(expense.id),
            after_json={"approval_status": expense.approval_status},
        )
        track_event(company_id=expense.company_id, actor_id=request.user.id, event_name="expense_approved", payload={"expense_id": expense.id})
        return Response(self.get_serializer(expense).data)

    @action(methods=["post"], detail=True)
    def reject(self, request, pk=None):
        expense = self.get_object()
        expense.approval_status = VehicleExpense.APPROVAL_REJECTED
        expense.save(update_fields=["approval_status", "updated_at"])
        AuditLog.objects.create(
            company_id=expense.company_id,
            actor_id=request.user.id,
            action="expense.reject",
            object_type="VehicleExpense",
            object_id=str(expense.id),
            after_json={"approval_status": expense.approval_status},
        )
        return Response(self.get_serializer(expense).data)

    @action(methods=["post"], detail=True)
    def pay(self, request, pk=None):
        expense = self.get_object()
        if expense.approval_status != VehicleExpense.APPROVAL_APPROVED:
            return Response({"detail": "Solo puedes pagar gastos aprobados."}, status=status.HTTP_400_BAD_REQUEST)
        expense.payment_status = VehicleExpense.PAYMENT_PAID
        expense.paid_by = request.user
        expense.save(update_fields=["payment_status", "paid_by", "updated_at"])
        AuditLog.objects.create(
            company_id=expense.company_id,
            actor_id=request.user.id,
            action="expense.pay",
            object_type="VehicleExpense",
            object_id=str(expense.id),
            after_json={"payment_status": expense.payment_status},
        )
        return Response(self.get_serializer(expense).data)


class VehicleExpenseAttachmentViewSet(ExpenseCapabilityViewSet):
    queryset = VehicleExpenseAttachment.objects.select_related("vehicle_expense", "attachment").all().order_by("-id")
    serializer_class = VehicleExpenseAttachmentSerializer

    def get_queryset(self):
        return super().get_queryset().filter(company_id=self._request_company_id())

    def perform_create(self, serializer):
        company_id = self._request_company_id()
        enforce_upload_limits(company_id=company_id, actor_id=self.request.user.id)
        serializer.save(company_id=company_id)
