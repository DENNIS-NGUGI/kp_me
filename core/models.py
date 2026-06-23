from django.db import models

class County(models.Model):
    """47 Kenyan Counties"""
    REGION_CHOICES = (
        ('coast', 'Coast'),
        ('eastern', 'Eastern'),
        ('north_eastern', 'North Eastern'),
        ('central', 'Central'),
        ('rift_valley', 'Rift Valley'),
        ('western', 'Western'),
        ('nairobi', 'Nairobi'),
    )
    
    code = models.CharField(max_length=3, unique=True, help_text="County code (001-047)")
    name = models.CharField(max_length=100, unique=True)
    headquarters = models.CharField(max_length=100)
    region = models.CharField(max_length=20, choices=REGION_CHOICES)
    population = models.BigIntegerField(null=True, blank=True)
    area_sq_km = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Counties"
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def get_subcounties(self):
        return self.subcounties.filter(is_active=True)


class SubCounty(models.Model):
    """Sub-Counties within Counties"""
    county = models.ForeignKey(County, on_delete=models.CASCADE, related_name='subcounties')
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    headquarters = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['county', 'name']
        unique_together = ['county', 'name']
        verbose_name_plural = "Sub-Counties"
    
    def __str__(self):
        return f"{self.name} ({self.county.name})"


class Quarter(models.Model):
    """Reporting Quarters - Configurable by Admin"""
    QUARTER_CHOICES = (
        (1, 'Q1 (Jan-Mar)'),
        (2, 'Q2 (Apr-Jun)'),
        (3, 'Q3 (Jul-Sep)'),
        (4, 'Q4 (Oct-Dec)'),
    )
    
    name = models.CharField(max_length=20, help_text="e.g., Q1 2025")
    fiscal_year = models.CharField(max_length=9, help_text="e.g., 2024/2025")
    quarter_number = models.IntegerField(choices=QUARTER_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    submission_deadline = models.DateField()
    is_active = models.BooleanField(default=True, help_text="Visible for data entry")
    is_closed = models.BooleanField(default=False, help_text="No more submissions allowed")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date']
        unique_together = ['quarter_number', 'fiscal_year']
    
    def __str__(self):
        return f"{self.name} ({self.fiscal_year})"
    
    def is_open_for_submission(self):
        """Check if quarter is open for new submissions"""
        from django.utils import timezone
        return self.is_active and not self.is_closed and timezone.now().date() <= self.submission_deadline
    
    def days_until_deadline(self):
        from django.utils import timezone
        delta = self.submission_deadline - timezone.now().date()
        return delta.days
