from datetime import date

from django.db import migrations, models


def fill_existing_send_dates(apps, schema_editor):
    Campaign = apps.get_model("campaigns", "Campaign")
    first_blast = date(2026, 9, 18)
    for campaign in Campaign.objects.filter(sms_sent_on__isnull=True):
        campaign.sms_sent_on = campaign.analysis_period_start or first_blast
        campaign.save(update_fields=["sms_sent_on"])


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaign",
            name="sms_sent_on",
            field=models.DateField(
                blank=True,
                db_index=True,
                help_text="Calendar date this blast was sent",
                null=True,
            ),
        ),
        migrations.AlterModelOptions(
            name="campaign",
            options={"ordering": ["-sms_sent_on", "-created_at"]},
        ),
        migrations.RunPython(fill_existing_send_dates, migrations.RunPython.noop),
    ]
