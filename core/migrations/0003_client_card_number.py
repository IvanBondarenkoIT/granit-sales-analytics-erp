from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_productparametervalue"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="card_number",
            field=models.CharField(
                blank=True, db_index=True, help_text="Loyalty card from ORGN.NAME", max_length=32
            ),
        ),
    ]
