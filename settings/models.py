from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class SystemSetting(models.Model):
    """System-wide configuration settings"""
    
    SETTING_TYPES = (
        ('string', 'String'),
        ('integer', 'Integer'),
        ('decimal', 'Decimal'),
        ('boolean', 'Boolean'),
        ('json', 'JSON'),
        ('text', 'Text'),
    )
    
    key = models.CharField(max_length=100, unique=True, help_text="Setting key e.g., APP_NAME")
    value = models.TextField(help_text="Setting value")
    setting_type = models.CharField(max_length=20, choices=SETTING_TYPES, default='string')
    description = models.TextField(blank=True, help_text="Description of what this setting does")
    
    # Metadata
    is_editable = models.BooleanField(default=True, help_text="Can be edited by admin")
    is_public = models.BooleanField(default=False, help_text="Visible to all users")
    
    # Audit
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['key']
        verbose_name = "System Setting"
        verbose_name_plural = "System Settings"
    
    def __str__(self):
        return f"{self.key} = {self.value[:50]}"
    
    def get_typed_value(self):
        """Return the value in the correct type"""
        if self.setting_type == 'boolean':
            return self.value.lower() in ['true', '1', 'yes', 'on']
        elif self.setting_type == 'integer':
            try:
                return int(self.value)
            except ValueError:
                return 0
        elif self.setting_type == 'decimal':
            try:
                return float(self.value)
            except ValueError:
                return 0.0
        elif self.setting_type == 'json':
            try:
                import json
                return json.loads(self.value)
            except:
                return {}
        return self.value