from django.db import models


class Store(models.Model):
    """Store dimension - Granit retail locations."""
    granit_id = models.IntegerField(unique=True, help_text="Store ID from Granit ERP")
    name = models.CharField(max_length=200)
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


class Product(models.Model):
    """Product dimension - Granit SKU."""
    granit_id = models.IntegerField(unique=True, help_text="Product/SKU ID from Granit ERP")
    name = models.CharField(max_length=500)
    group = models.ForeignKey(ProductGroup, on_delete=models.SET_NULL, null=True, related_name='products')
    parameter = models.ForeignKey(ProductParameter, on_delete=models.SET_NULL, null=True, related_name='products')
    is_active = models.BooleanField(default=True, help_text="Active SKU with sales or stock")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dim_product'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (ID: {self.granit_id})"
