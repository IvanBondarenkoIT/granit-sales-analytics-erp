from django.db import models
from core.models import Store, Client, Product


class SaleFact(models.Model):
    """Sales fact table - individual sale line items."""
    sale_date = models.DateField(db_index=True, help_text="Date of sale")
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='sales')
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='sales', null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='sales')
    
    quantity = models.DecimalField(max_digits=12, decimal_places=3, help_text="Quantity sold")
    amount = models.DecimalField(max_digits=15, decimal_places=2, help_text="Sale amount (money)")
    
    granit_sale_id = models.IntegerField(help_text="Sale document ID from Granit ERP", null=True)
    granit_line_id = models.IntegerField(help_text="Sale line ID from Granit ERP", null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fact_sale'
        ordering = ['-sale_date', 'store', 'product']
        indexes = [
            models.Index(fields=['sale_date', 'store']),
            models.Index(fields=['sale_date', 'product']),
            models.Index(fields=['sale_date', 'client']),
            models.Index(fields=['granit_sale_id', 'granit_line_id']),
        ]

    def __str__(self):
        return f"{self.sale_date} {self.product.name} x {self.quantity}"


class StockSnapshot(models.Model):
    """Stock snapshot - daily stock levels by SKU and store."""
    snapshot_date = models.DateField(db_index=True, help_text="Date of snapshot (yesterday)")
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='stock_snapshots')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='stock_snapshots')
    
    quantity = models.DecimalField(max_digits=12, decimal_places=3, help_text="Stock quantity")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fact_stock_snapshot'
        ordering = ['-snapshot_date', 'store', 'product']
        unique_together = [['snapshot_date', 'store', 'product']]
        indexes = [
            models.Index(fields=['snapshot_date', 'product']),
        ]

    def __str__(self):
        return f"{self.snapshot_date} {self.store.name} {self.product.name}: {self.quantity}"
