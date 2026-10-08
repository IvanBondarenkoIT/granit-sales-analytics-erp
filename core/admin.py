from django.contrib import admin

from .models import (
    Client,
    GranitWpMapping,
    Product,
    ProductCostSnapshot,
    ProductGroup,
    ProductParameter,
    ProductParameterValue,
    SiteCategory,
    SiteProduct,
    Store,
)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ["granit_id", "name", "kind", "created_at"]
    search_fields = ["name", "granit_id"]
    ordering = ["name"]


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ["granit_id", "name", "phone", "created_at"]
    search_fields = ["name", "phone", "granit_id"]
    ordering = ["name"]


@admin.register(ProductGroup)
class ProductGroupAdmin(admin.ModelAdmin):
    list_display = ["granit_id", "name", "parent", "parent_path", "created_at"]
    search_fields = ["name", "granit_id"]
    ordering = ["name"]
    raw_id_fields = ["parent"]


@admin.register(ProductParameter)
class ProductParameterAdmin(admin.ModelAdmin):
    list_display = ["granit_id", "name", "created_at"]
    search_fields = ["name", "granit_id"]
    ordering = ["name"]


@admin.register(ProductParameterValue)
class ProductParameterValueAdmin(admin.ModelAdmin):
    list_display = ["granit_id", "label", "parameter", "created_at"]
    list_filter = ["parameter"]
    search_fields = ["label", "granit_id"]
    ordering = ["label"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "granit_id",
        "name",
        "group",
        "parameter",
        "parameter_value",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "group", "parameter", "parameter_value"]
    search_fields = ["name", "granit_id"]
    ordering = ["name"]


@admin.register(GranitWpMapping)
class GranitWpMappingAdmin(admin.ModelAdmin):
    list_display = ["wp_product_id", "granit_id", "synced_at"]
    search_fields = ["wp_product_id", "granit_id"]


@admin.register(SiteCategory)
class SiteCategoryAdmin(admin.ModelAdmin):
    list_display = ["wp_category_id", "name", "parent", "count", "synced_at"]
    search_fields = ["wp_category_id", "name", "slug"]


@admin.register(SiteProduct)
class SiteProductAdmin(admin.ModelAdmin):
    list_display = [
        "wp_product_id",
        "name",
        "sku",
        "regular_price",
        "sale_price",
        "in_stock",
        "synced_at",
    ]
    search_fields = ["name", "sku", "wp_product_id"]


@admin.register(ProductCostSnapshot)
class ProductCostSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        "product",
        "snapshot_date",
        "last_cost",
        "avg_cost_90d",
        "stock_qty",
    ]
    list_filter = ["snapshot_date"]
    raw_id_fields = ["product"]
