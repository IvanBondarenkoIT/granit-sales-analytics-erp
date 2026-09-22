from django.contrib import admin
from .models import SaleFact, StockSnapshot


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
