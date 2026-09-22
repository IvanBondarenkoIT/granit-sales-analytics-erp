from django.contrib import admin
from .models import ETLRun, ETLWatermark


@admin.register(ETLRun)
class ETLRunAdmin(admin.ModelAdmin):
    list_display = ['etl_type', 'started_at', 'completed_at', 'status', 'records_processed', 'records_inserted', 'records_updated']
    list_filter = ['status', 'etl_type']
    date_hierarchy = 'started_at'
    ordering = ['-started_at']
    readonly_fields = ['started_at', 'completed_at']


@admin.register(ETLWatermark)
class ETLWatermarkAdmin(admin.ModelAdmin):
    list_display = ['entity_name', 'last_processed_date', 'last_processed_id', 'updated_at']
    search_fields = ['entity_name']
    ordering = ['entity_name']
