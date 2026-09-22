from datetime import date

from django import forms
from django.utils.translation import gettext_lazy as _


class CampaignUploadForm(forms.Form):
    name = forms.CharField(
        label=_("Campaign name"),
        max_length=200,
        help_text=_("Give each blast its own name so lists stay separate."),
    )
    sms_sent_on = forms.DateField(
        label=_("SMS sent on"),
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text=_("Date this mailing went out. Analysis starts on this day."),
    )
    date_to = forms.DateField(
        label=_("Analysis to (exclusive)"),
        initial=date.today,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    excel_file = forms.FileField(
        label=_("Excel file"),
        required=False,
        help_text=_("Client list for this blast only (customer_id + phone)."),
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
        if sent and date_to and date_to <= sent:
            raise forms.ValidationError(_("Analysis end must be after the SMS send date."))
        if not cleaned.get("use_local_file") and not cleaned.get("excel_file"):
            raise forms.ValidationError(_("Upload an Excel file or use the saved local list."))
        return cleaned
