import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_productgroup_parent"),
        ("sales", "0002_sale_line_unique"),
    ]

    operations = [
        migrations.CreateModel(
            name="SuperGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(max_length=64, unique=True)),
                ("title", models.CharField(max_length=200)),
                ("color", models.CharField(default="FFFFFF", help_text="Hex RGB without #", max_length=6)),
                ("sort_order", models.PositiveIntegerField(db_index=True, default=0)),
                (
                    "is_catchall",
                    models.BooleanField(
                        default=False,
                        help_text="Synthetic 'Outside super-groups' row; no membership rows",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "dim_super_group",
                "ordering": ["sort_order", "title"],
            },
        ),
        migrations.CreateModel(
            name="SuperGroupMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "product_group",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="super_group_member",
                        to="core.productgroup",
                    ),
                ),
                (
                    "super_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="members",
                        to="sales.supergroup",
                    ),
                ),
            ],
            options={
                "db_table": "dim_super_group_member",
                "ordering": ["super_group", "product_group__name"],
            },
        ),
    ]
