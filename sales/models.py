from django.db import models
from core.models import Store, Client, Product, ProductGroup


class SuperGroup(models.Model):
    """Shared product-group buckets for the sales matrix (same for all users)."""

    key = models.SlugField(max_length=64, unique=True)
    title = models.CharField(max_length=200)
    color = models.CharField(max_length=6, default="FFFFFF", help_text="Hex RGB without #")
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    is_catchall = models.BooleanField(
        default=False,
        help_text="Synthetic 'Outside super-groups' row; no membership rows",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dim_super_group"
        ordering = ["sort_order", "title"]

    def __str__(self):
        return self.title


class SuperGroupMember(models.Model):
    """One Granit product group belongs to at most one super-group."""

    super_group = models.ForeignKey(SuperGroup, on_delete=models.CASCADE, related_name="members")
    product_group = models.OneToOneField(
        ProductGroup,
        on_delete=models.CASCADE,
        related_name="super_group_member",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dim_super_group_member"
        ordering = ["super_group", "product_group__name"]

    def __str__(self):
        return f"{self.product_group.name} → {self.super_group.title}"


class SaleFact(models.Model):
    """Sales fact table - individual sale line items."""
    sale_date = models.DateField(db_index=True, help_text="Date of sale")
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='sales')
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='sales', null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='sales')
    
    quantity = models.DecimalField(max_digits=12, decimal_places=3, help_text="Quantity sold")
    amount = models.DecimalField(max_digits=15, decimal_places=2, help_text="Sale amount (money)")
    
    granit_sale_id = models.IntegerField(help_text="Sale document ID from Granit ERP")
    granit_line_id = models.IntegerField(help_text="Sale line ID from Granit ERP")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fact_sale'
        ordering = ['-sale_date', 'store', 'product']
        constraints = [
            models.UniqueConstraint(
                fields=['granit_sale_id', 'granit_line_id'],
                name='fact_sale_granit_line_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['sale_date', 'store']),
            models.Index(fields=['sale_date', 'product']),
            models.Index(fields=['sale_date', 'client']),
        ]

    def __str__(self):
        return f"{self.sale_date} {self.product.name} x {self.quantity}"


class StockSnapshot(models.Model):
    """Stock snapshot - daily stock levels by SKU and store."""
    snapshot_date = models.DateField(db_index=True, help_text="Date of snapshot (yesterday)")
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name='stock_snapshots',
        help_text="Company ledger store (granit_id=0) when stock is not per shop",
    )
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
