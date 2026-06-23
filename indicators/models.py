from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class ThematicArea(models.Model):
    """Thematic Areas (Previously called Categories)"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    sort_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Indicator(models.Model):
    """Master List of M&E Indicators"""
    DATA_TYPE_CHOICES = (
        ('numeric', 'Numeric'),
        ('percentage', 'Percentage'),
        ('decimal', 'Decimal'),
        ('boolean', 'Boolean'),
        ('count', 'Count'),
    )
    
    FREQUENCY_CHOICES = (
        ('annual', 'Annual'),
        ('quarterly', 'Quarterly'),
        ('monthly', 'Monthly'),
        ('5_years', '5 Years'),
        ('10_years', '10 Years'),
    )
    
    INDICATOR_TYPE_CHOICES = (
        ('impact', 'Impact'),
        ('outcome', 'Outcome'),
        ('output', 'Output'),
        ('action', 'Action/Programme'),
    )
    
    # Core fields
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255)
    thematic_area = models.ForeignKey(ThematicArea, on_delete=models.PROTECT, related_name='indicators')
    indicator_type = models.CharField(max_length=20, choices=INDICATOR_TYPE_CHOICES, default='output')
    description = models.TextField(blank=True)
    
    # Measurement
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES)
    unit = models.CharField(max_length=100, help_text="e.g., %, per 100,000, births per woman")
    formula = models.TextField(blank=True, help_text="Calculation formula if applicable")
    
    # Target & Source
    target_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    source_system = models.CharField(max_length=100, blank=True, help_text="e.g., KNBS, MOH, UNDP")
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    
    # ===== NEW: Range Validation Fields =====
    min_value = models.DecimalField(
        max_digits=20, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Minimum allowed value (leave blank for no minimum)"
    )
    max_value = models.DecimalField(
        max_digits=20, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Maximum allowed value (leave blank for no maximum)"
    )
    
    # Disaggregation
    disaggregation_by_age = models.BooleanField(default=False)
    disaggregation_by_sex = models.BooleanField(default=False)
    disaggregation_by_region = models.BooleanField(default=False)
    disaggregation_note = models.CharField(max_length=200, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_custom = models.BooleanField(default=False, help_text="Custom indicator added by project manager")
    notes = models.TextField(blank=True)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['thematic_area', 'code']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['thematic_area']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def get_indicator_type_display(self):
        return dict(self.INDICATOR_TYPE_CHOICES).get(self.indicator_type, self.indicator_type)
    
    def get_range_display(self):
        """Display the valid range for this indicator"""
        if self.min_value is not None and self.max_value is not None:
            return f"{self.min_value} - {self.max_value} {self.unit}"
        elif self.min_value is not None:
            return f"≥ {self.min_value} {self.unit}"
        elif self.max_value is not None:
            return f"≤ {self.max_value} {self.unit}"
        return "No range set"
    
    def validate_value(self, value_str):
        """
        Validate a value string against this indicator's rules.
        Returns: (is_valid, error_message)
        """
        if not value_str or value_str.strip() == '':
            return True, None
        
        value_str = value_str.strip()
        
        # Check data type first
        try:
            if self.data_type in ['numeric', 'count']:
                val = float(value_str)
                if not val.is_integer():
                    return False, f"Must be a whole number for {self.code}"
                if self.data_type == 'count' and val < 0:
                    return False, f"Count cannot be negative for {self.code}"
            elif self.data_type in ['percentage', 'decimal']:
                val = float(value_str)
            else:
                # For boolean/text, skip numeric validation
                return True, None
        except ValueError:
            return False, f"Must be a number for {self.code}"
        
        # Range validation
        if self.min_value is not None and val < float(self.min_value):
            return False, f"Value must be at least {self.min_value} {self.unit} for {self.code}"
        
        if self.max_value is not None and val > float(self.max_value):
            return False, f"Value must be at most {self.max_value} {self.unit} for {self.code}"
        
        # Percentage-specific check (even if max not set)
        if self.data_type == 'percentage' and (val < 0 or val > 100):
            return False, f"Percentage must be between 0 and 100 for {self.code}"
        
        return True, None