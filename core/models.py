from django.db import models


class Store(models.Model):
    """Store dimension: Granit receipt groups (STORGRP) and warehouses without one (STORLIST)."""
    KIND_GROUP = "group"
    KIND_WAREHOUSE = "warehouse"
    KIND_CHOICES = [
        (KIND_GROUP, "Receipt group (STORGRP)"),
        (KIND_WAREHOUSE, "Warehouse (STORLIST)"),
    ]

    granit_id = models.IntegerField(unique=True, help_text="Store ID from Granit ERP")
    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_GROUP)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dim_store'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (ID: {self.granit_id})"


class Client(models.Model):
    """Client dimension - Granit customers."""
    granit_id = models.IntegerField(unique=True, help_text="Client ID from Granit ERP")
    name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    card_number = models.CharField(
        max_length=32, blank=True, db_index=True, help_text="Loyalty card from ORGN.NAME"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dim_client'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (ID: {self.granit_id})"


class ProductGroup(models.Model):
    """Product group dimension - Granit product groups."""
    granit_id = models.IntegerField(unique=True, help_text="Group ID from Granit ERP")
    name = models.CharField(max_length=200)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        help_text="Parent group from GOODSGROUPS.PARENTID",
    )
    parent_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Cached name path e.g. DRINKS > Water",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dim_product_group'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (ID: {self.granit_id})"


class ProductParameter(models.Model):
    """Product parameter dimension - e.g. 'продукция' (id=2 in reference)."""
    granit_id = models.IntegerField(unique=True, help_text="Parameter ID from Granit ERP")
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dim_product_parameter'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (ID: {self.granit_id})"


class ProductParameterValue(models.Model):
    """Value of a product parameter (e.g. a «продукция» label)."""
    granit_id = models.IntegerField(unique=True, help_text="GDSPARAMVAL.ID from Granit ERP")
    parameter = models.ForeignKey(
        ProductParameter, on_delete=models.CASCADE, related_name='values'
    )
    label = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dim_product_parameter_value'
        ordering = ['label']

    def __str__(self):
        return f"{self.label} (ID: {self.granit_id})"


class Product(models.Model):
    """Product dimension - Granit SKU."""
    granit_id = models.IntegerField(unique=True, help_text="Product/SKU ID from Granit ERP")
    name = models.CharField(max_length=500)
    group = models.ForeignKey(ProductGroup, on_delete=models.SET_NULL, null=True, related_name='products')
    parameter = models.ForeignKey(
        ProductParameter, on_delete=models.SET_NULL, null=True, related_name='products'
    )
    parameter_value = models.ForeignKey(
        ProductParameterValue,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
    )
    is_active = models.BooleanField(default=True, help_text="Active SKU with sales or stock")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dim_product'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (ID: {self.granit_id})"


class GranitWpMapping(models.Model):
    """Link WooCommerce product id ↔ Granit GOODS.ID (from Google Sheets)."""

    wp_product_id = models.CharField(max_length=32, unique=True)
    granit_id = models.IntegerField(db_index=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "granit_wp_mapping"
        ordering = ["wp_product_id"]

    def __str__(self):
        return f"wp:{self.wp_product_id} → granit:{self.granit_id}"


class SiteCategory(models.Model):
    """WooCommerce product category (tree via parent)."""

    wp_category_id = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=300)
    slug = models.CharField(max_length=300, blank=True)
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children"
    )
    count = models.IntegerField(default=0)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "site_category"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} (wp:{self.wp_category_id})"


class SiteProduct(models.Model):
    """Snapshot of a WooCommerce catalog product."""

    categories = models.ManyToManyField(SiteCategory, blank=True, related_name="products")
    wp_product_id = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=500)
    sku = models.CharField(max_length=120, blank=True)
    url = models.URLField(max_length=500, blank=True)
    regular_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    sale_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    in_stock = models.BooleanField(default=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "site_product"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} (wp:{self.wp_product_id})"

    @property
    def effective_sale_price(self):
        return self.sale_price if self.sale_price is not None else self.regular_price


class ProductCostSnapshot(models.Model):
    """Last and 90-day average incoming cost + stock from Granit GDDKT."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cost_snapshots")
    snapshot_date = models.DateField()
    last_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    avg_cost_90d = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    stock_qty = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "product_cost_snapshot"
        ordering = ["-snapshot_date", "product_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "snapshot_date"],
                name="product_cost_snapshot_uniq",
            )
        ]

    def __str__(self):
        return f"{self.product_id} @ {self.snapshot_date}"
