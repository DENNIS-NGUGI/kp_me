from django.db import models
from django.contrib.auth.models import AbstractUser, Permission
from core.models import County
from datetime import timedelta
from django.utils import timezone

class Role(models.Model):
    """User Role - manages permissions"""
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100, blank=True, help_text="Friendly name shown to users")
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, blank=True)
    is_system = models.BooleanField(default=False, help_text="System role cannot be deleted")
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.get_display_name()
    
    def get_display_name(self):
        """Return the display name if set, otherwise format the name"""
        if self.display_name:
            return self.display_name
        # Format the name: county_me -> County M&E Officer
        name_map = {
            'admin': 'System Administrator',
            'ncpd_me': 'NCPD M&E Officer',
            'county_me': 'County M&E Officer',
            'partner': 'Partner Organization',
            'policy_maker': 'Policy Maker',
        }
        return name_map.get(self.name, self.name.replace('_', ' ').title())
    
    def user_count(self):
        return self.users.count()

class User(AbstractUser):
    """Extended User Model with Role as ForeignKey"""
    
    # Use Role as ForeignKey instead of CharField
    role = models.ForeignKey(
        'users.Role', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='users'
    )
    
    # OTP Fields
    otp_secret = models.CharField(max_length=50, blank=True, null=True)
    otp_created_at = models.DateTimeField(null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    
    county = models.ForeignKey(County, on_delete=models.SET_NULL, null=True, blank=True)
    organization = models.CharField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    is_verified = models.BooleanField(default=False)
    approved_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Audit fields
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    
    class Meta:
        ordering = ['username']
    
    def __str__(self):
        role_name = self.role.name if self.role else 'No Role'
        return f"{self.username} - {role_name}"
    
    def get_full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def get_role_display(self):
        return self.role.name if self.role else 'No Role Assigned'
    
    def has_module_permission(self, module, action='view'):
        """Check if user has permission for a specific module action"""
        if self.is_superuser:
            return True
        if not self.role:
            return False
        perm_codename = f"{action}_{module}"
        return self.role.permissions.filter(codename=perm_codename).exists()
    
    def can_approve_data(self):
        if not self.role:
            return False
        return self.role.name in ['admin', 'ncpd_me']
    
    def can_manage_indicators(self):
        if not self.role:
            return False
        return self.role.name in ['admin', 'ncpd_me']
    
    def can_manage_users(self):
        if not self.role:
            return False
        return self.role.name == 'admin'
    
    def can_manage_roles(self):
        if not self.role:
            return False
        return self.role.name == 'admin'
    
    def generate_otp(self):
        """Generate a 6-digit OTP"""
        self.otp_secret = ''.join(random.choices(string.digits, k=6))
        self.otp_created_at = timezone.now()
        self.save()
        return self.otp_secret
    
    def verify_otp(self, otp):
        """Verify the OTP"""
        if not self.otp_secret or not self.otp_created_at:
            return False
        
        # OTP expires after 10 minutes
        expiry = self.otp_created_at + timedelta(minutes=10)
        if timezone.now() > expiry:
            return False
        
        return self.otp_secret == otp
    
    def is_account_locked(self):
        """Check if account is locked due to too many login attempts"""
        if self.locked_until and timezone.now() < self.locked_until:
            return True
        return False
    
    def reset_login_attempts(self):
        """Reset login attempts after successful login"""
        self.login_attempts = 0
        self.locked_until = None
        self.save()
    
    def increment_login_attempts(self):
        """Increment login attempts and lock account if needed"""
        self.login_attempts += 1
        if self.login_attempts >= 5:
            self.locked_until = timezone.now() + timedelta(minutes=30)
        self.save()

class AuditLog(models.Model):
    """Audit Trail for all user actions"""
    ACTION_CHOICES = (
        ('CREATE', 'Create'),
        ('READ', 'Read'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('APPROVE', 'Approve'),
        ('REJECT', 'Reject'),
        ('SUBMIT', 'Submit'),
        ('EXPORT', 'Export'),
        ('IMPORT', 'Import'),
    )
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100, help_text="e.g., User, DataEntry")
    object_id = models.CharField(max_length=100, blank=True)
    object_repr = models.CharField(max_length=200, blank=True, help_text="String representation")
    changes = models.JSONField(default=dict, blank=True, help_text="Before/After changes")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['model_name', 'timestamp']),
            models.Index(fields=['action']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action} at {self.timestamp}"