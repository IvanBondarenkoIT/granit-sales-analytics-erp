from django.db import models
from core.models import Product, ProductGroup


class Promo(models.Model):
    """Promotion tracking - evaluate promo effectiveness."""
    
    name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    
    pre_period_days = models.IntegerField(default=14, help_text="Days before promo for baseline")
    
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'promo'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} ({self.start_date} to {self.end_date})"


class PromoProduct(models.Model):
    """Products or groups in the promotion."""
    
    promo = models.ForeignKey(Promo, on_delete=models.CASCADE, related_name='promo_products')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True, related_name='promos')
    product_group = models.ForeignKey(ProductGroup, on_delete=models.PROTECT, null=True, blank=True, related_name='promos')

    class Meta:
        db_table = 'promo_product'
        ordering = ['promo']

    def __str__(self):
        target = self.product.name if self.product else self.product_group.name
        return f"{self.promo.name} - {target}"


class PromoAnalysis(models.Model):
    """Promo analysis results - daily sales vs baselines."""
    
    promo = models.ForeignKey(Promo, on_delete=models.CASCADE, related_name='analyses')
    analysis_date = models.DateField()
    
    actual_sales = models.DecimalField(max_digits=15, decimal_places=2)
    baseline_pre_period = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    baseline_yoy = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    forecast_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'promo_analysis'
        ordering = ['promo', 'analysis_date']
        unique_together = [['promo', 'analysis_date']]

    def __str__(self):
        return f"{self.promo.name} - {self.analysis_date}"
