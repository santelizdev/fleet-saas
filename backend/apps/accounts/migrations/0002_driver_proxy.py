from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Driver",
            fields=[],
            options={
                "verbose_name": "Conductor",
                "verbose_name_plural": "Conductores",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("accounts.user",),
        ),
    ]
