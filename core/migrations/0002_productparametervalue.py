import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductParameterValue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('granit_id', models.IntegerField(help_text='GDSPARAMVAL.ID from Granit ERP', unique=True)),
                ('label', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('parameter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='values', to='core.productparameter')),
            ],
            options={
                'db_table': 'dim_product_parameter_value',
                'ordering': ['label'],
            },
        ),
        migrations.AddField(
            model_name='product',
            name='parameter_value',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='products', to='core.productparametervalue'),
        ),
    ]
