import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL("DELETE FROM fact_sale WHERE granit_sale_id IS NULL OR granit_line_id IS NULL;", migrations.RunSQL.noop),
        migrations.AlterField(
            model_name='salefact',
            name='granit_line_id',
            field=models.IntegerField(help_text='Sale line ID from Granit ERP'),
        ),
        migrations.AlterField(
            model_name='salefact',
            name='granit_sale_id',
            field=models.IntegerField(help_text='Sale document ID from Granit ERP'),
        ),
        migrations.RemoveIndex(
            model_name='salefact',
            name='fact_sale_granit__85d18e_idx',
        ),
        migrations.AddConstraint(
            model_name='salefact',
            constraint=models.UniqueConstraint(fields=('granit_sale_id', 'granit_line_id'), name='fact_sale_granit_line_uniq'),
        ),
        migrations.AlterField(
            model_name='stocksnapshot',
            name='store',
            field=models.ForeignKey(
                help_text='Company ledger store (granit_id=0) when stock is not per shop',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='stock_snapshots',
                to='core.store',
            ),
        ),
    ]
