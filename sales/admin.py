from django.contrib import admin

from .models import SaleFact, StockSnapshot, SuperGroup, SuperGroupMember


@admin.register(SaleFact)
class SaleFactAdmin(admin.ModelAdmin):
    list_display = ['sale_date', 'store', 'product', 'quantity', 'amount', 'client']
    list_filter = ['sale_date', 'store']
    search_fields = ['product__name', 'client__name']
    date_hierarchy = 'sale_date'
    ordering = ['-sale_date']


@admin.register(StockSnapshot)
class StockSnapshotAdmin(admin.ModelAdmin):
    list_display = ['snapshot_date', 'store', 'product', 'quantity']
    list_filter = ['snapshot_date', 'store']
    search_fields = ['product__name']
    date_hierarchy = 'snapshot_date'
    ordering = ['-snapshot_date']


class SuperGroupMemberInline(admin.TabularInline):
    model = SuperGroupMember
    extra = 0
    autocomplete_fields = ["product_group"]


@admin.register(SuperGroup)
class SuperGroupAdmin(admin.ModelAdmin):
    list_display = ["title", "key", "color", "sort_order", "is_catchall"]
    list_editable = ["sort_order", "color"]
    search_fields = ["title", "key"]
    inlines = [SuperGroupMemberInline]


@admin.register(SuperGroupMember)
class SuperGroupMemberAdmin(admin.ModelAdmin):
    list_display = ["super_group", "product_group"]
    list_filter = ["super_group"]
    search_fields = ["product_group__name", "super_group__title"]
    autocomplete_fields = ["product_group", "super_group"]
