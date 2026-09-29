from datetime import date

from django import forms
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from core.models import Product, ProductGroup
from promos.excel import LOCAL_PROMOS_XLSX


class PromoForm(forms.Form):
    name = forms.CharField(
        label=_("Promo name"),
        max_length=200,
        required=False,
        help_text=_("Used when the file has no name column, or for a manual promo."),
    )
    start_date = forms.DateField(
        label=_("Promo start"),
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text=_("Fills empty start_date cells in the file."),
    )
    end_date = forms.DateField(
        label=_("Promo end"),
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text=_("The end date is included. Fills empty end_date cells in the file."),
    )
    pre_period_days = forms.IntegerField(
        label=_("Baseline days before promo"),
        min_value=1,
        max_value=365,
        initial=14,
        help_text=_("Median of daily sales in this window is the pre-period baseline."),
    )
    excel_file = forms.FileField(
        label=_("Promo table (Excel)"),
        required=False,
        help_text=_("Columns: name, start_date, end_date, group_id, product_id. group_id and product_id are Granit IDs."),
    )
    use_example_file = forms.BooleanField(
        label=_("Use example promo file"),
        required=False,
        initial=False,
        help_text=_("Local example with Candies group and Ballerina SKU (not required in git)."),
    )
    notes = forms.CharField(
        label=_("Notes"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    groups = forms.ModelMultipleChoiceField(
        label=_("Product groups"),
        queryset=ProductGroup.objects.order_by("name"),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 8}),
    )
    products = forms.ModelMultipleChoiceField(
        label=_("Products"),
        queryset=Product.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 8}),
        help_text=_("Optional if you upload a file. The list narrows to the selected groups."),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        group_ids = []
        if self.data:
            group_ids = self.data.getlist("groups")
        elif self.initial.get("groups"):
            group_ids = [str(pk) for pk in self.initial["groups"]]
        products = Product.objects.order_by("name")
        if group_ids:
            self.fields["products"].queryset = products.filter(group_id__in=group_ids)
        else:
            self.fields["products"].queryset = Product.objects.none()
        self.fields["groups"].widget.attrs.update(
            {
                "hx-get": reverse("promo_product_options"),
                "hx-target": "#id_products",
                "hx-swap": "outerHTML",
                "hx-trigger": "change",
            }
        )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        has_file = bool(cleaned.get("excel_file") or (cleaned.get("use_example_file") and LOCAL_PROMOS_XLSX.is_file()))
        has_targets = bool(cleaned.get("groups") or cleaned.get("products"))
        if start and end and end < start:
            raise forms.ValidationError(_("Promo end must be on or after the start date."))
        if not has_file and not has_targets:
            raise forms.ValidationError(_("Upload a promo table or select at least one product group or product."))
        if not has_file:
            if not cleaned.get("name"):
                raise forms.ValidationError(_("Enter a promo name or upload a table."))
            if not start or not end:
                raise forms.ValidationError(_("Enter promo dates or upload a table."))
        if cleaned.get("use_example_file") and not LOCAL_PROMOS_XLSX.is_file() and not cleaned.get("excel_file"):
            raise forms.ValidationError(_("Example promo file is not on this machine."))
        return cleaned

    def date_defaults(self):
        today = date.today()
        self.fields["end_date"].initial = today
        self.fields["start_date"].initial = today
        return self
