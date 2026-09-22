from django.contrib import admin
from .models import Campaign, CampaignClient


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'sms_sent_on', 'created_at', 'total_clients', 'clients_with_sales', 'analysis_period_start', 'analysis_period_end']
    search_fields = ['name']
    list_filter = ['sms_sent_on']
    date_hierarchy = 'sms_sent_on'
    ordering = ['-created_at']


@admin.register(CampaignClient)
class CampaignClientAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'granit_client_id', 'phone', 'had_sales', 'sales_amount']
    list_filter = ['campaign', 'had_sales']
    search_fields = ['granit_client_id', 'phone']
    ordering = ['campaign', 'granit_client_id']
