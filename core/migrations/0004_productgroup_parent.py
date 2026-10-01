import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_client_card_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="productgroup",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                help_text="Parent group from GOODSGROUPS.PARENTID",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="children",
                to="core.productgroup",
            ),
        ),
        migrations.AddField(
            model_name="productgroup",
            name="parent_path",
            field=models.CharField(
                blank=True,
                help_text="Cached name path e.g. DRINKS > Water",
                max_length=500,
            ),
        ),
    ]
