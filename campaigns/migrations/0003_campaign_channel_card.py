from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0002_campaign_sms_sent_on"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaign",
            name="channel",
            field=models.CharField(
                choices=[("sms", "SMS"), ("telegram", "Telegram bot")],
                db_index=True,
                default="sms",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="campaignclient",
            name="card_number",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AlterField(
            model_name="campaignclient",
            name="granit_client_id",
            field=models.IntegerField(
                blank=True, help_text="Granit client ID (from file or matched by card)", null=True
            ),
        ),
    ]
