from datetime import date

from django import forms
from django.utils.translation import gettext_lazy as _

from campaigns.models import Campaign


class CampaignUploadForm(forms.Form):
    name = forms.CharField(
        label=_("Campaign name"),
        max_length=200,
        help_text=_("Give each blast its own name so lists stay separate."),
    )
    channel = forms.ChoiceField(
        label=_("Channel"),
        choices=[
            (Campaign.CHANNEL_SMS, _("SMS")),
            (Campaign.CHANNEL_TELEGRAM, _("Telegram bot")),
        ],
        initial=Campaign.CHANNEL_SMS,
    )
    sms_sent_on = forms.DateField(
        label=_("Sent on"),
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text=_("Date this mailing went out. Analysis starts on this day."),
    )
    date_to = forms.DateField(
        label=_("Analysis to (exclusive)"),
        initial=date.today,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    excel_file = forms.FileField(
        label=_("Client list file"),
        required=False,
        help_text=_("SMS: Excel with customer_id + phone. Telegram bot: CSV with card number + phone."),
    )
    use_local_file = forms.BooleanField(
        label=_("Use saved local SMS list"),
        required=False,
        initial=False,
        help_text=_("Only for the 18 Sep 2026 blast already stored on this machine."),
    )
    notes = forms.CharField(label=_("Notes"), required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        cleaned = super().clean()
        sent = cleaned.get("sms_sent_on")
        date_to = cleaned.get("date_to")
        channel = cleaned.get("channel")
        upload = cleaned.get("excel_file")
        if sent and date_to and date_to <= sent:
            raise forms.ValidationError(_("Analysis end must be after the send date."))
        if channel == Campaign.CHANNEL_TELEGRAM:
            if cleaned.get("use_local_file"):
                raise forms.ValidationError(_("The saved local list is for SMS only."))
            if not upload:
                raise forms.ValidationError(_("Upload the Telegram bot CSV file."))
            if not upload.name.lower().endswith(".csv"):
                raise forms.ValidationError(_("Telegram bot list must be a .csv file."))
        else:
            if not cleaned.get("use_local_file") and not upload:
                raise forms.ValidationError(_("Upload an Excel file or use the saved local list."))
            if upload and not upload.name.lower().endswith(".xlsx"):
                raise forms.ValidationError(_("SMS list must be an .xlsx file."))
        return cleaned
