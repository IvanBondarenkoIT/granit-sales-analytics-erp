from django.db import models
from core.models import Client


class Campaign(models.Model):
    """One SMS blast. Each mailing is its own row — never merge lists."""
    
    name = models.CharField(max_length=200)
    sms_sent_on = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Calendar date this blast was sent",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_file = models.FileField(upload_to='campaigns/', null=True, blank=True)
    
    analysis_period_start = models.DateField(null=True, blank=True)
    analysis_period_end = models.DateField(null=True, blank=True)
    
    total_clients = models.IntegerField(default=0)
    clients_with_sales = models.IntegerField(default=0)
    
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'campaign'
        ordering = ['-sms_sent_on', '-created_at']

    def __str__(self):
        sent = self.sms_sent_on.isoformat() if self.sms_sent_on else self.created_at.strftime('%Y-%m-%d')
        return f"{self.name} ({sent})"


class CampaignClient(models.Model):
    """Campaign client mapping - which clients were in the campaign."""
    
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='campaign_clients')
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='campaigns', null=True, blank=True)
    
    granit_client_id = models.IntegerField(help_text="Client ID from uploaded Excel")
    phone = models.CharField(max_length=50, blank=True)
    
    had_sales = models.BooleanField(default=False)
    sales_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        db_table = 'campaign_client'
        ordering = ['campaign', 'granit_client_id']
        unique_together = [['campaign', 'granit_client_id']]

    def __str__(self):
        return f"{self.campaign.name} - Client {self.granit_client_id}"
