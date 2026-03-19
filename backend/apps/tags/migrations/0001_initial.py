# Generated manually for the TAG / pórticos MVP.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("companies", "0002_companylimit"),
        ("vehicles", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TollRoad",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("code", models.CharField(blank=True, default="", max_length=32)),
                ("operator_name", models.CharField(blank=True, default="", max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="toll_roads", to="companies.company")),
            ],
            options={"verbose_name": "Autopista", "verbose_name_plural": "Autopistas"},
        ),
        migrations.CreateModel(
            name="TagImportBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_name", models.CharField(max_length=120)),
                ("source_file_name", models.CharField(blank=True, default="", max_length=255)),
                ("period_start", models.DateField(blank=True, null=True)),
                ("period_end", models.DateField(blank=True, null=True)),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
                ("status", models.CharField(choices=[("pending", "Pendiente"), ("processed", "Procesado"), ("failed", "Con errores")], default="pending", max_length=16)),
                ("notes", models.TextField(blank=True, default="")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tag_import_batches", to="companies.company")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tag_import_batches", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Importación TAG", "verbose_name_plural": "Importaciones TAG"},
        ),
        migrations.CreateModel(
            name="TollGate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=32)),
                ("name", models.CharField(max_length=120)),
                ("direction", models.CharField(blank=True, default="", max_length=64)),
                ("km_marker", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="toll_gates", to="companies.company")),
                ("road", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="gates", to="tags.tollroad")),
            ],
            options={"verbose_name": "Pórtico", "verbose_name_plural": "Pórticos"},
        ),
        migrations.CreateModel(
            name="TagTransit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("detected_plate", models.CharField(blank=True, default="", max_length=16)),
                ("transit_at", models.DateTimeField()),
                ("transit_date", models.DateField()),
                ("amount_clp", models.PositiveIntegerField(default=0)),
                ("currency", models.CharField(default="CLP", max_length=8)),
                ("match_status", models.CharField(choices=[("pending", "Pendiente"), ("matched", "Conciliado"), ("unmatched", "Sin vehículo"), ("observed", "Observado")], default="pending", max_length=16)),
                ("notes", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("batch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="transits", to="tags.tagimportbatch")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tag_transits", to="companies.company")),
                ("gate", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="transits", to="tags.tollgate")),
                ("road", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transits", to="tags.tollroad")),
                ("vehicle", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tag_transits", to="vehicles.vehicle")),
            ],
            options={"verbose_name": "Tránsito TAG", "verbose_name_plural": "Tránsitos TAG"},
        ),
        migrations.CreateModel(
            name="TagCharge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("detected_plate", models.CharField(blank=True, default="", max_length=16)),
                ("charge_date", models.DateField()),
                ("billed_at", models.DateTimeField(blank=True, null=True)),
                ("amount_clp", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("pending", "Pendiente"), ("reconciled", "Conciliado"), ("unmatched", "Sin vehículo"), ("disputed", "Observado")], default="pending", max_length=16)),
                ("notes", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("batch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="charges", to="tags.tagimportbatch")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tag_charges", to="companies.company")),
                ("gate", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="charges", to="tags.tollgate")),
                ("road", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="charges", to="tags.tollroad")),
                ("transit", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="charges", to="tags.tagtransit")),
                ("vehicle", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tag_charges", to="vehicles.vehicle")),
            ],
            options={"verbose_name": "Cobro TAG", "verbose_name_plural": "Cobros TAG"},
        ),
        migrations.AddIndex(model_name="tollroad", index=models.Index(fields=["company", "name"], name="tags_tollro_company_53f6e1_idx")),
        migrations.AddConstraint(model_name="tollroad", constraint=models.UniqueConstraint(fields=("company", "name"), name="uniq_toll_road_company_name")),
        migrations.AddIndex(model_name="tagimportbatch", index=models.Index(fields=["company", "imported_at"], name="tags_tagimp_company_17c9bc_idx")),
        migrations.AddIndex(model_name="tollgate", index=models.Index(fields=["company", "road"], name="tags_tollga_company_3fd1ab_idx")),
        migrations.AddIndex(model_name="tollgate", index=models.Index(fields=["company", "code"], name="tags_tollga_company_f0d8b8_idx")),
        migrations.AddConstraint(model_name="tollgate", constraint=models.UniqueConstraint(fields=("company", "road", "code"), name="uniq_toll_gate_company_road_code")),
        migrations.AddIndex(model_name="tagtransit", index=models.Index(fields=["company", "transit_date"], name="tags_tagtra_company_1c59f5_idx")),
        migrations.AddIndex(model_name="tagtransit", index=models.Index(fields=["company", "vehicle", "transit_date"], name="tags_tagtra_company_447650_idx")),
        migrations.AddIndex(model_name="tagtransit", index=models.Index(fields=["company", "detected_plate"], name="tags_tagtra_company_c8b161_idx")),
        migrations.AddIndex(model_name="tagcharge", index=models.Index(fields=["company", "charge_date"], name="tags_tagcha_company_63ed9c_idx")),
        migrations.AddIndex(model_name="tagcharge", index=models.Index(fields=["company", "vehicle", "charge_date"], name="tags_tagcha_company_004aaa_idx")),
        migrations.AddIndex(model_name="tagcharge", index=models.Index(fields=["company", "status"], name="tags_tagcha_company_7bd0cb_idx")),
    ]
