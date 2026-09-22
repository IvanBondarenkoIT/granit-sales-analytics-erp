from django.db import models


class ETLRun(models.Model):
    """ETL execution tracking - nightly runs from firebird-db-proxy."""
    
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    
    etl_type = models.CharField(max_length=50, help_text="Type: incremental, backfill, dimensions")
    records_processed = models.IntegerField(default=0)
    records_inserted = models.IntegerField(default=0)
    records_updated = models.IntegerField(default=0)
    
    error_message = models.TextField(blank=True)
    log_details = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'etl_run'
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.etl_type} - {self.started_at.strftime('%Y-%m-%d %H:%M')} - {self.status}"


class ETLWatermark(models.Model):
    """ETL watermark - track last processed date/id for incremental loads."""
    
    entity_name = models.CharField(max_length=50, unique=True, help_text="Entity: sales, stock, etc")
    last_processed_date = models.DateField(null=True, blank=True)
    last_processed_id = models.IntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'etl_watermark'
        ordering = ['entity_name']

    def __str__(self):
        return f"{self.entity_name} - last: {self.last_processed_date or self.last_processed_id}"
