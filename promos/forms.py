from datetime import date

from django import forms
from django.db.models import Count
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
    promo_type = forms.CharField(label=_("Type"), max_length=120, required=False)
    format = forms.CharField(label=_("Format"), max_length=200, required=False)
    channels = forms.CharField(label=_("Channels / locations"), max_length=300, required=False)
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
        help_text=_("Average daily sales in this window (days without sales count as zero) is the pre-period baseline."),
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
    product_ids = forms.ModelMultipleChoiceField(
        label=_("Promo products"),
        queryset=Product.objects.all(),
        required=False,
        widget=forms.MultipleHiddenInput,
    )
    group_ids = forms.ModelMultipleChoiceField(
        label=_("Product groups"),
        queryset=ProductGroup.objects.all(),
        required=False,
        widget=forms.MultipleHiddenInput,
    )

    def __init__(self, *args, promo=None, **kwargs):
        self.promo = promo
        if promo is not None:
            initial = kwargs.setdefault("initial", {})
            rows = list(promo.promo_products.all())
            initial.update(
                {
                    "name": promo.name,
                    "promo_type": promo.promo_type,
                    "format": promo.format,
                    "channels": promo.channels,
                    "start_date": promo.start_date,
                    "end_date": promo.end_date,
                    "pre_period_days": promo.pre_period_days,
                    "notes": promo.notes,
                    "product_ids": [r.product_id for r in rows if r.product_id],
                    "group_ids": [r.product_group_id for r in rows if r.product_group_id],
                }
            )
        super().__init__(*args, **kwargs)
        if promo is not None:
            del self.fields["excel_file"]
            del self.fields["use_example_file"]

    def _selected_pks(self, name: str) -> list[int]:
        if self.is_bound:
            raw = self.data.getlist(name)
        else:
            raw = self.initial.get(name) or []
        out = []
        for value in raw:
            try:
                out.append(int(value))
            except (TypeError, ValueError):
                continue
        return list(dict.fromkeys(out))

    def selected_product_items(self) -> list[dict]:
        from promos.picker import product_items

        pks = self._selected_pks("product_ids")
        by_pk = Product.objects.in_bulk(pks)
        return product_items(by_pk[pk] for pk in pks if pk in by_pk)

    def selected_groups(self) -> list[ProductGroup]:
        pks = self._selected_pks("group_ids")
        groups = ProductGroup.objects.annotate(n_products=Count("products")).in_bulk(pks)
        return [groups[pk] for pk in pks if pk in groups]

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        has_file = bool(cleaned.get("excel_file") or (cleaned.get("use_example_file") and LOCAL_PROMOS_XLSX.is_file()))
        has_targets = bool(cleaned.get("product_ids") or cleaned.get("group_ids"))
        if start and end and end < start:
            raise forms.ValidationError(_("Promo end must be on or after the start date."))
        if not has_file and not has_targets:
            raise forms.ValidationError(
                _("Upload a promo table or select at least one product group or product.")
            )
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
