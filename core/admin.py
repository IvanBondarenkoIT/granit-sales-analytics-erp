from django.contrib import admin
from .models import Store, Client, Product, ProductGroup, ProductParameter


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ['granit_id', 'name', 'created_at']
    search_fields = ['name', 'granit_id']
    ordering = ['name']


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['granit_id', 'name', 'phone', 'created_at']
    search_fields = ['name', 'phone', 'granit_id']
    ordering = ['name']


@admin.register(ProductGroup)
class ProductGroupAdmin(admin.ModelAdmin):
    list_display = ['granit_id', 'name', 'created_at']
    search_fields = ['name', 'granit_id']
    ordering = ['name']


@admin.register(ProductParameter)
class ProductParameterAdmin(admin.ModelAdmin):
    list_display = ['granit_id', 'name', 'created_at']
    search_fields = ['name', 'granit_id']
    ordering = ['name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['granit_id', 'name', 'group', 'parameter', 'is_active', 'created_at']
    list_filter = ['is_active', 'group', 'parameter']
    search_fields = ['name', 'granit_id']
    ordering = ['name']
