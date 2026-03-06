from rest_framework import serializers

from apps.vehicles.models import Vehicle


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            "id",
            "company",
            "branch",
            "plate",
            "brand",
            "model",
            "year",
            "vin",
            "engine_number",
            "current_km",
            "status",
            "assigned_driver",
            "created_at",
        ]
        read_only_fields = ["id", "company", "created_at"]


class VehicleCSVImportSerializer(serializers.Serializer):
    csv_content = serializers.CharField()
