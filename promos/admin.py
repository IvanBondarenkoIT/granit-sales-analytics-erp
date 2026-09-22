from django.contrib import admin
from .models import Promo, PromoProduct, PromoAnalysis


@admin.register(Promo)
class PromoAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'pre_period_days', 'created_at']
    search_fields = ['name']
    date_hierarchy = 'start_date'
    ordering = ['-start_date']


@admin.register(PromoProduct)
class PromoProductAdmin(admin.ModelAdmin):
    list_display = ['promo', 'product', 'product_group']
    list_filter = ['promo']
    search_fields = ['product__name', 'product_group__name']
    ordering = ['promo']


@admin.register(PromoAnalysis)
class PromoAnalysisAdmin(admin.ModelAdmin):
    list_display = ['promo', 'analysis_date', 'actual_sales', 'baseline_pre_period', 'baseline_yoy', 'forecast_value']
    list_filter = ['promo']
    date_hierarchy = 'analysis_date'
    ordering = ['promo', 'analysis_date']
