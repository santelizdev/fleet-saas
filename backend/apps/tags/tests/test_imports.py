from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.companies.models import Company
from apps.tags.models import TagCharge, TagImportBatch, TagTransit, TollGate, TollRoad
from apps.tags.services import import_manual_tag_csv
from apps.vehicles.models import Vehicle


class TagManualImportServiceTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="RutaCore TAG", rut="11.222.333-4")
        self.user = User.objects.create_superuser(
            email="tag-admin@local.test",
            password="Secret123!",
            name="Tag Admin",
            company=self.company,
        )
        self.vehicle = Vehicle.objects.create(company=self.company, plate="FGFP86")
        self.csv_content = "\n".join(
            [
                'Patente;FechaHora;Portico;Concesionaria;TAG;Horario;Importe;Factura',
                'FG-FP86;20/02/2026 21:10:00;"P4 PO";"CN";"24360058705";"TBFP";"413,02";"BOLETA EXENTA - 118692715"',
                'FGFP86;21/02/2026 09:15:00;"P3 PO";"CN";"24360058705";"TBFP";"306,02";"BOLETA EXENTA - 118692715"',
                'fgfp86;21/02/2026 09:15:00;"P3 PO";"CN";"24360058705";"TBFP";"306,02";"BOLETA EXENTA - 118692715"',
            ]
        )

    def test_import_manual_csv_creates_batches_charges_and_weekend_split(self):
        upload = SimpleUploadedFile("detalle.csv", self.csv_content.encode("utf-8"), content_type="text/csv")

        result = import_manual_tag_csv(
            company=self.company,
            vehicle=self.vehicle,
            uploaded_file=upload,
            source_name="Cartola manual",
            created_by=self.user,
        )

        self.assertEqual(result.created_charges, 2)
        self.assertEqual(result.created_transits, 2)
        self.assertEqual(result.matched_items, 2)
        self.assertEqual(result.unmatched_items, 0)
        self.assertEqual(result.duplicate_count, 1)
        self.assertEqual(result.error_count, 0)

        batch = TagImportBatch.objects.get(pk=result.batch.pk)
        self.assertEqual(batch.total_rows, 3)
        self.assertEqual(str(batch.period_start), "2026-02-20")
        self.assertEqual(str(batch.period_end), "2026-02-21")

        self.assertEqual(TollRoad.objects.count(), 1)
        self.assertEqual(TollGate.objects.count(), 2)
        self.assertEqual(TagTransit.objects.count(), 2)
        self.assertEqual(TagCharge.objects.count(), 2)

        weekday_charge = TagCharge.objects.get(detected_plate="FGFP86", charge_date="2026-02-20")
        weekend_charge = TagCharge.objects.get(detected_plate="FGFP86", charge_date="2026-02-21")

        self.assertFalse(weekday_charge.is_weekend)
        self.assertTrue(weekend_charge.is_weekend)
        self.assertEqual(weekday_charge.schedule_code, "TBFP")
        self.assertEqual(weekday_charge.tag_reference, "24360058705")
        self.assertEqual(weekday_charge.invoice_reference, "BOLETA EXENTA - 118692715")
        self.assertEqual(weekday_charge.amount_clp, 413)
        self.assertEqual(weekday_charge.vehicle, self.vehicle)
        self.assertEqual(weekend_charge.vehicle, self.vehicle)

    def test_import_manual_csv_rejects_mismatched_plate(self):
        upload = SimpleUploadedFile(
            "detalle.csv",
            "\n".join(
                [
                    'Patente;FechaHora;Portico;Concesionaria;TAG;Horario;Importe;Factura',
                    'ZZZZ99;20/02/2026 21:10:00;"P4 PO";"CN";"24360058705";"TBFP";"413,02";"BOLETA EXENTA - 118692715"',
                ]
            ).encode("utf-8"),
            content_type="text/csv",
        )

        with self.assertRaisesMessage(ValueError, "no coincide con el vehículo seleccionado"):
            import_manual_tag_csv(
                company=self.company,
                vehicle=self.vehicle,
                uploaded_file=upload,
                source_name="Cartola errónea",
                created_by=self.user,
            )

    def test_import_manual_csv_skips_rows_already_loaded(self):
        first_upload = SimpleUploadedFile("detalle.csv", self.csv_content.encode("utf-8"), content_type="text/csv")
        second_upload = SimpleUploadedFile("detalle.csv", self.csv_content.encode("utf-8"), content_type="text/csv")

        first_result = import_manual_tag_csv(
            company=self.company,
            vehicle=self.vehicle,
            uploaded_file=first_upload,
            source_name="Cartola manual",
            created_by=self.user,
        )
        second_result = import_manual_tag_csv(
            company=self.company,
            vehicle=self.vehicle,
            uploaded_file=second_upload,
            source_name="Cartola manual repetida",
            created_by=self.user,
        )

        self.assertEqual(first_result.created_charges, 2)
        self.assertEqual(second_result.created_charges, 0)
        self.assertEqual(second_result.duplicate_count, 3)
        self.assertEqual(TagCharge.objects.count(), 2)
        self.assertEqual(TagTransit.objects.count(), 2)


class TagAnalyticsViewTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="RutaCore TAG", rut="44.555.666-7")
        self.other_company = Company.objects.create(name="RutaCore TAG 2", rut="55.666.777-8")
        self.user = User.objects.create_superuser(
            email="tag-analytics@local.test",
            password="Secret123!",
            name="Tag Analytics",
            company=self.company,
        )
        self.vehicle = Vehicle.objects.create(company=self.company, plate="FGFP86")
        self.other_vehicle = Vehicle.objects.create(company=self.other_company, plate="HJKL90")
        upload = SimpleUploadedFile(
            "detalle.csv",
            "\n".join(
                [
                    'Patente;FechaHora;Portico;Concesionaria;TAG;Horario;Importe;Factura',
                    'FGFP86;20/02/2026 21:10:00;"P4 PO";"CN";"24360058705";"TBFP";"413,02";"BOLETA EXENTA - 118692715"',
                    'FGFP86;21/02/2026 09:15:00;"P3 PO";"CN";"24360058705";"TBFP";"306,02";"BOLETA EXENTA - 118692715"',
                ]
            ).encode("utf-8"),
            content_type="text/csv",
        )
        import_manual_tag_csv(
            company=self.company,
            vehicle=self.vehicle,
            uploaded_file=upload,
            source_name="Cartola analytics",
            created_by=self.user,
        )

    def test_analytics_supports_month_and_plate_filters(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("admin:tags_tagcharge_analytics"),
            {"month": "2026-02", "plate": "FGFP86"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Control manual de cobros TAG")
        self.assertContains(response, "FGFP86")
        self.assertContains(response, "Fin de semana")
        self.assertContains(response, "Total del período filtrado")
        self.assertContains(response, "Duplicados")

    def test_company_scope_populates_only_related_vehicles_in_import_form(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("admin:tags_tagcharge_analytics"),
            {"company_scope": str(self.other_company.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{self.other_company.id}" selected')
        self.assertContains(response, "HJKL90")
        self.assertNotContains(response, "FGFP86</option>")

    def test_post_with_mismatched_vehicle_returns_form_error_instead_of_500(self):
        self.client.force_login(self.user)
        upload = SimpleUploadedFile(
            "detalle.csv",
            "\n".join(
                [
                    'Patente;FechaHora;Portico;Concesionaria;TAG;Horario;Importe;Factura',
                    'FGFP86;20/02/2026 21:10:00;"P4 PO";"CN";"24360058705";"TBFP";"413,02";"BOLETA EXENTA - 118692715"',
                ]
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(
            f"{reverse('admin:tags_tagcharge_analytics')}?company_scope={self.other_company.id}",
            {
                "source_name": "Cartola inválida",
                "company": str(self.other_company.id),
                "vehicle": str(self.other_vehicle.id),
                "csv_file": upload,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no coincide con el vehículo seleccionado")
        self.assertContains(response, "data-tag-import-error")
