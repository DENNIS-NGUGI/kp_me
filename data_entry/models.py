from django.db import models
from django.core.exceptions import ValidationError
from core.models import County, Quarter
from indicators.models import Indicator
from django.contrib.auth import get_user_model

User = get_user_model()

class DataEntry(models.Model):
    """Data Entry Records - Unique per County + Quarter + Indicator"""
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    # Core fields - UNIQUE together
    county = models.ForeignKey(County, on_delete=models.CASCADE, related_name='data_entries')
    quarter = models.ForeignKey(Quarter, on_delete=models.CASCADE, related_name='data_entries')
    indicator = models.ForeignKey(Indicator, on_delete=models.CASCADE, related_name='data_entries')
    
    # Value - stored as text but validated based on indicator data type
    value = models.CharField(max_length=255, blank=True, null=True, 
                             help_text="The actual data value (blank if data not available)")
    
    # Target at submission time (for historical accuracy)
    target_at_submission = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True,
                                               help_text="Target value when this was submitted")
    
    # Status workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_locked = models.BooleanField(default=False, help_text="Locked when approved")
    
    # Metadata
    notes = models.TextField(blank=True, help_text="Any additional notes about this data entry")
    
    # Submission & Approval tracking
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                     related_name='submitted_entries')
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='approved_entries')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, help_text="Reason if rejected")

    # Audit
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    
    class Meta:
        ordering = ['county', 'quarter', 'indicator']
        unique_together = ['county', 'quarter', 'indicator']
        indexes = [
            models.Index(fields=['county', 'quarter', 'status']),
            models.Index(fields=['indicator', 'status']),
        ]
    
    def __str__(self):
        return f"{self.county.name} - {self.quarter.name} - {self.indicator.code}"
    
    def clean(self):
        """Validate value using indicator's validation rules"""
        if not self.value:
            return
        
        # Use the indicator's validate_value method
        is_valid, error_message = self.indicator.validate_value(self.value)
        if not is_valid:
            raise ValidationError({'value': error_message})
    
    def save(self, *args, **kwargs):
        # Run validation
        self.full_clean()
        
        # Save target at submission time when submitted
        if self.status == 'submitted' and not self.target_at_submission:
            self.target_at_submission = self.indicator.target_value
        super().save(*args, **kwargs)
    
    def get_value_display(self):
        """Return formatted value with unit"""
        if not self.value:
            return "No Data"
        return f"{self.value} {self.indicator.unit if self.indicator.unit else ''}"
    
    def is_met(self):
        """Check if value meets target"""
        if not self.value or not self.target_at_submission:
            return None
        try:
            val = float(self.value)
            target = float(self.target_at_submission)
            if self.indicator.code.startswith('FERT-') and self.indicator.code != 'FERT-01':
                return val <= target
            else:
                return val >= target
        except:
            return None
    
    # ============================================================
    # PERMISSION METHODS - Using users.permissions
    # ============================================================
    
    def can_edit(self, user):
        """Check if user can edit this entry"""
        return user.can_edit_data_entry(self)
    
    def can_submit(self, user):
        """Check if user can submit this entry"""
        return user.can_submit_data_entry(self)
    
    def can_approve(self, user):
        """Check if user can approve this entry"""
        return user.can_approve_data_entry(self)
    
    def can_delete(self, user):
        """Check if user can delete this entry"""
        return user.can_delete_data_entry(self)
    
    def can_view(self, user):
        """Check if user can view this entry"""
        return user.can_view_data_entry(self)