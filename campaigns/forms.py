from datetime import date, timedelta

from django import forms
from django.utils.translation import gettext_lazy as _

from campaigns.analysis import DEFAULT_SMS_SENT_ON


class CampaignUploadForm(forms.Form):
    name = forms.CharField(label=_("Campaign name"), max_length=200)
    excel_file = forms.FileField(label=_("Excel file"), required=False)
    use_local_file = forms.BooleanField(
        label=_("Use saved local SMS list"),
        required=False,
        initial=True,
    )
    date_from = forms.DateField(
        label=_("Analysis from"),
        initial=DEFAULT_SMS_SENT_ON,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        label=_("Analysis to (exclusive)"),
        initial=date.today(),
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    notes = forms.CharField(label=_("Notes"), required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("date_from") and cleaned.get("date_to"):
            if cleaned["date_to"] <= cleaned["date_from"]:
                raise forms.ValidationError(_("Analysis end must be after start."))
        if not cleaned.get("use_local_file") and not cleaned.get("excel_file"):
            raise forms.ValidationError(_("Upload an Excel file or use the saved local list."))
        return cleaned
