import secrets
import string
import hashlib
import hmac
from datetime import timedelta
from typing import Optional, List, Set

from django.db import models
from django.contrib.auth.models import AbstractUser, Permission
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from .constants import AuthConstants
from .managers import UserManager


class RoleManager(models.Manager):
    """Custom manager for Role model"""
    
    def get_or_create_system_role(self):
        """Get or create the system admin role"""
        role, created = self.get_or_create(
            name='admin',
            defaults={
                'display_name': 'System Administrator',
                'description': 'System Administrator with all permissions',
                'is_system': True,
                'is_active': True,
                'priority': 100,
            }
        )
        if created:
            # Assign all permissions
            all_perms = Permission.objects.all()
            role.permissions.set(all_perms)
        return role
    
    def get_active_roles(self):
        """Get all active roles"""
        return self.filter(is_active=True)


class Role(models.Model):
    """
    User Role - manages permissions - FULLY DATABASE DRIVEN
    """
    name = models.CharField(
        max_length=100, 
        unique=True,
        help_text=_("System name for the role (e.g., 'admin', 'data_entry')")
    )
    display_name = models.CharField(
        max_length=100, 
        blank=True, 
        help_text=_("Friendly name shown to users")
    )
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(
        Permission, 
        blank=True,
        related_name='roles'
    )
    is_system = models.BooleanField(
        default=False, 
        help_text=_("System role cannot be deleted")
    )
    is_active = models.BooleanField(default=True)
    icon = models.CharField(
        max_length=50, 
        blank=True, 
        help_text=_("Bootstrap icon name (e.g., 'bi-person')")
    )
    color = models.CharField(
        max_length=20, 
        blank=True, 
        help_text=_("CSS color class (e.g., 'primary', 'success')")
    )
    priority = models.PositiveSmallIntegerField(
        default=0,
        help_text=_("Higher priority roles can manage lower priority roles")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = RoleManager()
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name', 'is_active']),
            models.Index(fields=['priority']),
        ]
        verbose_name = _('Role')
        verbose_name_plural = _('Roles')
    
    def __str__(self) -> str:
        return self.get_display_name()
    
    def clean(self):
        if self.is_system and not self.is_active:
            raise ValidationError(_('System roles cannot be deactivated'))
        if self.is_system and self.name not in ['admin', 'superuser', 'system']:
            raise ValidationError(_('System roles must be named admin, superuser, or system'))
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def get_display_name(self) -> str:
        return self.display_name or self.name.replace('_', ' ').title()
    
    def user_count(self) -> int:
        return self.users.count()
    
    def has_permission(self, codename: str) -> bool:
        return self.permissions.filter(codename=codename).exists()
    
    def has_module_permission(self, module: str, action: str = 'view') -> bool:
        perm_codename = f"{action}_{module}"
        return self.has_permission(perm_codename)
    
    def get_all_permissions(self) -> List[str]:
        return list(self.permissions.values_list('codename', flat=True))
    
    def can_manage(self, target_role) -> bool:
        if not target_role or not target_role.is_active:
            return False
        return self.priority > target_role.priority or self.is_system


class User(AbstractUser):
    """
    Extended User Model with Role-based permissions
    """
    
    # Role relationship
    role = models.ForeignKey(
        'users.Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text=_("User's role for permissions")
    )
    
    # OTP Fields
    otp_secret = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=_("Hashed OTP for secure verification")
    )
    otp_created_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text=_("Timestamp when OTP was generated")
    )
    otp_attempts = models.PositiveSmallIntegerField(
        default=0,
        help_text=_("Number of failed OTP attempts")
    )
    is_email_verified = models.BooleanField(
        default=False,
        help_text=_("Whether the user's email has been verified")
    )
    email_verified_at = models.DateTimeField(
        null=True, 
        blank=True
    )
    
    # Security fields
    login_attempts = models.PositiveSmallIntegerField(
        default=0,
        help_text=_("Number of consecutive failed login attempts")
    )
    locked_until = models.DateTimeField(
        null=True, 
        blank=True,
        help_text=_("Account lockout expiry timestamp")
    )
    last_login_ip = models.GenericIPAddressField(
        null=True, 
        blank=True
    )
    last_login_user_agent = models.TextField(
        blank=True,
        help_text=_("User agent of last login")
    )
    
    # Profile fields
    county = models.ForeignKey(
        'core.County',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text=_("County this user belongs to")
    )
    organization = models.CharField(
        max_length=200, 
        blank=True,
        help_text=_("Organization name")
    )
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        validators=[
            RegexValidator(
                AuthConstants.PHONE_REGEX,
                message=_("Enter a valid phone number (e.g., +254712345678)")
            )
        ],
        help_text=_("Phone number with country code")
    )
    
    # Verification fields
    is_verified = models.BooleanField(
        default=False,
        help_text=_("Whether the user's account has been verified by an admin")
    )
    approved_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_users',
        help_text=_("Admin who approved this user")
    )
    approved_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text=_("Timestamp when user was approved")
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    deleted_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text=_("Soft delete timestamp")
    )
    
    objects = UserManager()

    class Meta:
        ordering = ['username']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role', 'is_active']),
            models.Index(fields=['county']),
            models.Index(fields=['is_verified', 'is_active']),
            models.Index(fields=['deleted_at']),
        ]
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        permissions = [
            # ================================================================
            # CUSTOM MODULE PERMISSIONS (Modules with NO model)
            # These MUST be defined here because Django doesn't auto-generate them
            # ================================================================
            
            # Dashboard - NO model exists
            ('view_dashboard', _('Can view dashboard')),
            ('add_dashboard', _('Can add dashboard')),
            ('change_dashboard', _('Can change dashboard')),
            ('delete_dashboard', _('Can delete dashboard')),
            
            # Reports - NO model exists
            ('view_reports', _('Can view reports')),
            ('add_reports', _('Can add reports')),
            ('change_reports', _('Can change reports')),
            ('delete_reports', _('Can delete reports')),
            ('export_reports', _('Can export reports')),
            
            # ================================================================
            # CUSTOM PERMISSIONS (can_ prefix)
            # These are NOT auto-generated by Django
            # ================================================================
            
            ('can_manage_users', _('Can manage users')),
            ('can_manage_roles', _('Can manage roles')),
            ('can_manage_system_settings', _('Can manage system settings')),
            ('can_approve_data', _('Can approve data')),
            ('can_manage_indicators', _('Can manage indicators')),
            ('can_manage_thematic_areas', _('Can manage thematic areas')),
            ('can_import_data', _('Can import data')),
            ('can_manage_partners', _('Can manage partners')),
            ('can_manage_projects', _('Can manage projects')),
            ('can_manage_county_data', _('Can manage county data')),
            
            # ================================================================
            # MODEL PERMISSIONS - NOT DEFINED HERE
            # Django auto-generates these for every model:
            # ================================================================
            # 
            # DataEntry model → view_dataentry, add_dataentry, change_dataentry, delete_dataentry
            # Indicator model → view_indicator, add_indicator, change_indicator, delete_indicator
            # Partner model → view_partner, add_partner, change_partner, delete_partner
            # Project model → view_project, add_project, change_project, delete_project
            # User model → view_user, add_user, change_user, delete_user
            # SystemSetting model → view_systemsetting, add_systemsetting, change_systemsetting, delete_systemsetting
            # AuditLog model → view_auditlog, add_auditlog, change_auditlog, delete_auditlog
            # County model → view_county, add_county, change_county, delete_county
            # Quarter model → view_quarter, add_quarter, change_quarter, delete_quarter
            # ThematicArea model → view_thematicarea, add_thematicarea, change_thematicarea, delete_thematicarea
            # 
            # DO NOT define these here - Django creates them automatically!
            # ================================================================
        ]
    
    def __str__(self) -> str:
        role_name = self.role.get_display_name() if self.role else 'No Role'
        return f"{self.username} ({role_name})"
    
    def clean(self):
        super().clean()
        if self.approved_by and self.approved_by.pk == self.pk:
            raise ValidationError(_('A user cannot approve themselves'))
    
    def save(self, *args, **kwargs):
        self.full_clean()
        if self.is_verified and self.approved_by and not self.approved_at:
            self.approved_at = timezone.now()
        super().save(*args, **kwargs)
    
    def delete(self, using=None, keep_parents=False):
        """Soft delete"""
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(using=using)
    
    def hard_delete(self, using=None, keep_parents=False):
        """Permanently delete"""
        super().delete(using=using, keep_parents=keep_parents)
    
    def get_full_name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def get_short_name(self) -> str:
        if self.first_name:
            return self.first_name
        return self.username
    
    def get_role_display(self) -> str:
        return self.role.get_display_name() if self.role else _('No Role Assigned')
    
    def get_absolute_url(self) -> str:
        from django.urls import reverse
        return reverse('users:detail', kwargs={'pk': self.pk})
    
    # ========================================================================
    # PERMISSION METHODS
    # ========================================================================
    
    def has_permission(self, codename: str) -> bool:
        if self.is_superuser:
            return True
        if not self.is_active or self.deleted_at:
            return False
        if not self.role or not self.role.is_active:
            return False
        return self.role.has_permission(codename)
    
    def has_module_permission(self, module: str, action: str = 'view') -> bool:
        if self.is_superuser:
            return True
        
        # Map module names to Django's auto-generated permission names
        # For modules with models, Django auto-generates: action_modelname
        # For modules without models, we use the custom defined permissions
        model_mapping = {
            # Modules with models (Django auto-generates)
            'data_entry': 'dataentry',
            'indicators': 'indicator',
            'partners': 'partner',
            'projects': 'project',
            'users': 'user',
            'settings': 'systemsetting',
            'audit_log': 'auditlog',
            'county': 'county',
            'quarter': 'quarter',
            'thematic_area': 'thematicarea',
            'subcounty': 'subcounty',
            'logentry': 'logentry',
            'group': 'group',
            'permission': 'permission',
            'session': 'session',
            'contenttype': 'contenttype',
            'role': 'role',
            'captchastore': 'captchastore',
            'emaildevice': 'emaildevice',
            'notification': 'notification',
            'notificationpreference': 'notificationpreference',
            'projectmilestone': 'projectmilestone',
            'projectreport': 'projectreport',
            
            # Modules without models (custom permissions)
            'dashboard': f"{action}_dashboard",
            'reports': f"{action}_reports",
        }
        
        model_name = model_mapping.get(module)
        if model_name is None:
            # Fallback: use the module name as-is
            perm_codename = f"{action}_{module}"
        elif module in ['dashboard', 'reports']:
            # These are custom permissions (no model)
            perm_codename = model_name
        else:
            # Django auto-generated permission
            perm_codename = f"{action}_{model_name}"
        
        return self.has_permission(perm_codename)
    
    def has_any_permission(self, *codenames: str) -> bool:
        if self.is_superuser:
            return True
        if not self.role or not self.role.is_active:
            return False
        return self.role.permissions.filter(codename__in=codenames).exists()
    
    def has_all_permissions(self, *codenames: str) -> bool:
        if self.is_superuser:
            return True
        if not self.role or not self.role.is_active:
            return False
        user_codenames = set(
            self.role.permissions.values_list('codename', flat=True)
        )
        return all(codename in user_codenames for codename in codenames)
    
    def get_all_permissions(self) -> Set[str]:
        if self.is_superuser:
            return set(Permission.objects.values_list('codename', flat=True))
        if not self.role:
            return set()
        return set(self.role.permissions.values_list('codename', flat=True))
    
    def can_manage_user(self, target_user) -> bool:
        if not target_user or self.pk == target_user.pk:
            return False
        if target_user.is_superuser:
            return False
        if self.is_superuser:
            return True
        if not self.role or not target_user.role:
            return False
        return self.role.can_manage(target_user.role)
    
    # ========================================================================
    # USER TYPE PROPERTIES
    # ========================================================================
    
    @property
    def is_county_user(self) -> bool:
        if not self.is_active or self.deleted_at:
            return False
        return (
            self.has_permission('can_manage_county_data') and 
            self.county is not None
        )
    
    @property
    def is_ncpd_user(self) -> bool:
        if not self.is_active or self.deleted_at:
            return False
        return (
            self.has_permission('can_approve_data') and 
            not self.is_county_user
        )
    
    @property
    def is_admin_user(self) -> bool:
        if not self.is_active or self.deleted_at:
            return False
        return (
            self.has_permission('can_manage_users') or 
            self.has_permission('can_manage_roles')
        )
    
    # ========================================================================
    # MODULE PERMISSION PROPERTIES
    # ========================================================================
    
    # ----- CUSTOM MODULE PERMISSIONS (No model - defined in Meta) -----
    
    @property
    def can_view_dashboard(self) -> bool:
        return self.has_permission('view_dashboard')
    
    @property
    def can_add_dashboard(self) -> bool:
        return self.has_permission('add_dashboard')
    
    @property
    def can_change_dashboard(self) -> bool:
        return self.has_permission('change_dashboard')
    
    @property
    def can_delete_dashboard(self) -> bool:
        return self.has_permission('delete_dashboard')
    
    @property
    def can_view_reports(self) -> bool:
        return self.has_permission('view_reports')
    
    @property
    def can_add_reports(self) -> bool:
        return self.has_permission('add_reports')
    
    @property
    def can_change_reports(self) -> bool:
        return self.has_permission('change_reports')
    
    @property
    def can_delete_reports(self) -> bool:
        return self.has_permission('delete_reports')
    
    @property
    def can_export_reports(self) -> bool:
        return self.has_permission('export_reports')
    
    # ----- DJANGO AUTO-GENERATED PERMISSIONS (Models exist) -----
    # These use Django's auto-generated names: action_modelname (NO underscore)
    
    @property
    def can_view_data_entry(self) -> bool:
        return self.has_permission('view_dataentry')
    
    @property
    def can_add_data_entry(self) -> bool:
        return self.has_permission('add_dataentry')
    
    @property
    def can_change_data_entry(self) -> bool:
        return self.has_permission('change_dataentry')
    
    @property
    def can_delete_data_entry(self) -> bool:
        return self.has_permission('delete_dataentry')
    
    @property
    def can_view_indicators(self) -> bool:
        return self.has_permission('view_indicator')
    
    @property
    def can_add_indicators(self) -> bool:
        return self.has_permission('add_indicator')
    
    @property
    def can_change_indicators(self) -> bool:
        return self.has_permission('change_indicator')
    
    @property
    def can_delete_indicators(self) -> bool:
        return self.has_permission('delete_indicator')
    
    @property
    def can_view_partners(self) -> bool:
        return self.has_permission('view_partner')
    
    @property
    def can_add_partners(self) -> bool:
        return self.has_permission('add_partner')
    
    @property
    def can_change_partners(self) -> bool:
        return self.has_permission('change_partner')
    
    @property
    def can_delete_partners(self) -> bool:
        return self.has_permission('delete_partner')
    
    @property
    def can_view_projects(self) -> bool:
        return self.has_permission('view_project')
    
    @property
    def can_add_projects(self) -> bool:
        return self.has_permission('add_project')
    
    @property
    def can_change_projects(self) -> bool:
        return self.has_permission('change_project')
    
    @property
    def can_delete_projects(self) -> bool:
        return self.has_permission('delete_project')
    
    @property
    def can_view_users(self) -> bool:
        return self.has_permission('view_user')
    
    @property
    def can_add_users(self) -> bool:
        return self.has_permission('add_user')
    
    @property
    def can_change_users(self) -> bool:
        return self.has_permission('change_user')
    
    @property
    def can_delete_users(self) -> bool:
        return self.has_permission('delete_user')
    
    @property
    def can_view_settings(self) -> bool:
        return self.has_permission('view_systemsetting')
    
    @property
    def can_add_settings(self) -> bool:
        return self.has_permission('add_systemsetting')
    
    @property
    def can_change_settings(self) -> bool:
        return self.has_permission('change_systemsetting')
    
    @property
    def can_delete_settings(self) -> bool:
        return self.has_permission('delete_systemsetting')
    
    @property
    def can_view_audit_log(self) -> bool:
        return self.has_permission('view_auditlog')
    
    @property
    def can_add_audit_log(self) -> bool:
        return self.has_permission('add_auditlog')
    
    @property
    def can_change_audit_log(self) -> bool:
        return self.has_permission('change_auditlog')
    
    @property
    def can_delete_audit_log(self) -> bool:
        return self.has_permission('delete_auditlog')
    
    @property
    def can_view_county(self) -> bool:
        return self.has_permission('view_county')
    
    @property
    def can_add_county(self) -> bool:
        return self.has_permission('add_county')
    
    @property
    def can_change_county(self) -> bool:
        return self.has_permission('change_county')
    
    @property
    def can_delete_county(self) -> bool:
        return self.has_permission('delete_county')
    
    @property
    def can_view_quarter(self) -> bool:
        return self.has_permission('view_quarter')
    
    @property
    def can_add_quarter(self) -> bool:
        return self.has_permission('add_quarter')
    
    @property
    def can_change_quarter(self) -> bool:
        return self.has_permission('change_quarter')
    
    @property
    def can_delete_quarter(self) -> bool:
        return self.has_permission('delete_quarter')
    
    @property
    def can_view_thematic_area(self) -> bool:
        return self.has_permission('view_thematicarea')
    
    @property
    def can_add_thematic_area(self) -> bool:
        return self.has_permission('add_thematicarea')
    
    @property
    def can_change_thematic_area(self) -> bool:
        return self.has_permission('change_thematicarea')
    
    @property
    def can_delete_thematic_area(self) -> bool:
        return self.has_permission('delete_thematicarea')
    
    # ========================================================================
    # CUSTOM PERMISSION PROPERTIES
    # ========================================================================
    
    @property
    def can_manage_users(self) -> bool:
        return self.has_permission('can_manage_users')
    
    @property
    def can_manage_roles(self) -> bool:
        return self.has_permission('can_manage_roles')
    
    @property
    def can_manage_system_settings(self) -> bool:
        return self.has_permission('can_manage_system_settings')
    
    @property
    def can_approve_data(self) -> bool:
        return self.has_permission('can_approve_data')
    
    @property
    def can_manage_indicators(self) -> bool:
        return self.has_permission('can_manage_indicators')
    
    @property
    def can_manage_thematic_areas(self) -> bool:
        return self.has_permission('can_manage_thematic_areas')
    
    @property
    def can_import_data(self) -> bool:
        return self.has_permission('can_import_data')
    
    @property
    def can_manage_partners(self) -> bool:
        return self.has_permission('can_manage_partners')
    
    @property
    def can_manage_projects(self) -> bool:
        return self.has_permission('can_manage_projects')
    
    @property
    def can_view_county_data(self) -> bool:
        return self.has_permission('view_county')
    
    @property
    def can_manage_county_data(self) -> bool:
        return self.has_permission('can_manage_county_data')
    
    # ========================================================================
    # OTP METHODS
    # ========================================================================
    
    def generate_otp(self) -> str:
        """Generate a cryptographically secure OTP"""
        otp = ''.join(secrets.choice(string.digits) for _ in range(AuthConstants.OTP_LENGTH))
        
        # Hash the OTP for storage
        secret_key = settings.SECRET_KEY.encode('utf-8')
        otp_hash = hmac.new(
            secret_key,
            otp.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        self.otp_secret = otp_hash
        self.otp_created_at = timezone.now()
        self.otp_attempts = 0
        self.save(update_fields=['otp_secret', 'otp_created_at', 'otp_attempts'])
        
        return otp
    
    def verify_otp(self, otp: str) -> bool:
        """Verify OTP with rate limiting"""
        if not self.otp_secret or not self.otp_created_at:
            return False
        
        # Check expiry
        expiry = self.otp_created_at + timedelta(minutes=AuthConstants.OTP_EXPIRY_MINUTES)
        if timezone.now() > expiry:
            return False
        
        # Check attempts
        if self.otp_attempts >= AuthConstants.OTP_MAX_ATTEMPTS:
            return False
        
        # Verify using constant-time comparison
        secret_key = settings.SECRET_KEY.encode('utf-8')
        expected_hash = self.otp_secret
        actual_hash = hmac.new(
            secret_key,
            otp.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        is_valid = hmac.compare_digest(actual_hash, expected_hash)
        
        if is_valid:
            self.otp_secret = None
            self.otp_created_at = None
            self.otp_attempts = 0
            self.save(update_fields=['otp_secret', 'otp_created_at', 'otp_attempts'])
        else:
            self.otp_attempts += 1
            self.save(update_fields=['otp_attempts'])
        
        return is_valid
    
    def clear_otp(self) -> None:
        """Clear OTP without verification"""
        self.otp_secret = None
        self.otp_created_at = None
        self.otp_attempts = 0
        self.save(update_fields=['otp_secret', 'otp_created_at', 'otp_attempts'])
    
    # ========================================================================
    # ACCOUNT LOCKOUT METHODS
    # ========================================================================
    
    def is_account_locked(self) -> bool:
        if self.locked_until and timezone.now() < self.locked_until:
            return True
        return False
    
    def get_lockout_remaining(self) -> Optional[timedelta]:
        if not self.locked_until:
            return None
        remaining = self.locked_until - timezone.now()
        if remaining.total_seconds() <= 0:
            return None
        return remaining
    
    def reset_login_attempts(self) -> None:
        self.login_attempts = 0
        self.locked_until = None
        self.save(update_fields=['login_attempts', 'locked_until'])
    
    def increment_login_attempts(self) -> bool:
        self.login_attempts += 1
        if self.login_attempts >= AuthConstants.MAX_LOGIN_ATTEMPTS:
            self.locked_until = timezone.now() + AuthConstants.LOCKOUT_DURATION
            is_locked = True
        else:
            is_locked = False
        self.save(update_fields=['login_attempts', 'locked_until'])
        return is_locked

    # ========================================================================
    # DATA ENTRY PERMISSION METHODS
    # ========================================================================
    
    def can_view_data_entry(self, entry):
        """Check if user can view a data entry"""
        from users.permissions import can_view_data_entry
        return can_view_data_entry(self, entry)
    
    def can_edit_data_entry(self, entry):
        """Check if user can edit a data entry"""
        from users.permissions import can_edit_data_entry
        return can_edit_data_entry(self, entry)
    
    def can_submit_data_entry(self, entry):
        """Check if user can submit a data entry"""
        from users.permissions import can_submit_data_entry
        return can_submit_data_entry(self, entry)
    
    def can_approve_data_entry(self, entry):
        """Check if user can approve a data entry"""
        from users.permissions import can_approve_data_entry
        return can_approve_data_entry(self, entry)
    
    def can_delete_data_entry(self, entry):
        """Check if user can delete a data entry"""
        from users.permissions import can_delete_data_entry
        return can_delete_data_entry(self, entry)
    
    def get_data_entry_filter(self):
        """Get the filter for data entry querysets"""
        from users.permissions import get_data_entry_queryset_filter
        return get_data_entry_queryset_filter(self)
    
    def get_data_scope(self):
        """Get the data scope for this user"""
        from users.permissions import get_user_data_scope
        return get_user_data_scope(self)

    # ========================================================================
    # PARTNER PERMISSION METHODS
    # ========================================================================
    
    def can_view_partners(self):
        """Check if user can view partners"""
        from users.permissions import can_view_partners
        return can_view_partners(self)
    
    def can_manage_partners(self):
        """Check if user can manage partners"""
        from users.permissions import can_manage_partners
        return can_manage_partners(self)
    
    def can_view_projects(self):
        """Check if user can view projects"""
        from users.permissions import can_view_projects
        return can_view_projects(self)
    
    def can_manage_projects(self):
        """Check if user can manage projects"""
        from users.permissions import can_manage_projects
        return can_manage_projects(self)
    
    def get_partner_filter(self):
        """Get filter for partner querysets"""
        from users.permissions import get_partner_queryset_filter
        return get_partner_queryset_filter(self)
    
    def get_project_filter(self):
        """Get filter for project querysets"""
        from users.permissions import get_project_queryset_filter
        return get_project_queryset_filter(self)
    
    @property
    def is_partner_user(self):
        """Check if user is a partner user"""
        return self.role and self.role.name == 'partner'


class AuditLog(models.Model):
    """Audit Trail for all user actions"""
    
    class Action(models.TextChoices):
        CREATE = 'CREATE', _('Create')
        READ = 'READ', _('Read')
        UPDATE = 'UPDATE', _('Update')
        DELETE = 'DELETE', _('Delete')
        LOGIN = 'LOGIN', _('Login')
        LOGOUT = 'LOGOUT', _('Logout')
        APPROVE = 'APPROVE', _('Approve')
        REJECT = 'REJECT', _('Reject')
        SUBMIT = 'SUBMIT', _('Submit')
        EXPORT = 'EXPORT', _('Export')
        IMPORT = 'IMPORT', _('Import')
        VIEW = 'VIEW', _('View')
        DOWNLOAD = 'DOWNLOAD', _('Download')
        UPLOAD = 'UPLOAD', _('Upload')
        RESET = 'RESET', _('Reset')
        FAILED = 'FAILED', _('Failed')
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    model_name = models.CharField(
        max_length=100,
        help_text=_("e.g., User, DataEntry")
    )
    object_id = models.CharField(max_length=100, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['model_name', 'timestamp']),
            models.Index(fields=['action']),
            models.Index(fields=['model_name', 'object_id']),
        ]
        verbose_name = _('Audit Log')
        verbose_name_plural = _('Audit Logs')
    
    def __str__(self) -> str:
        user_str = self.user.username if self.user else 'Anonymous'
        return f"{user_str} - {self.get_action_display()} at {self.timestamp}"
    
    @classmethod
    def log(cls, user, action, model_instance=None, changes=None, 
            request=None, extra_data=None, **kwargs):
        """Convenience method to create audit log entry"""
        data = {
            'user': user,
            'action': action,
            'extra_data': extra_data or {},
        }
        
        if model_instance:
            data['model_name'] = model_instance.__class__.__name__
            data['object_id'] = str(model_instance.pk)
            data['object_repr'] = str(model_instance)
        
        if changes:
            data['changes'] = changes
        
        if request:
            data['ip_address'] = request.META.get('REMOTE_ADDR')
            data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
            data['request_path'] = request.path
            data['request_method'] = request.method
        
        data.update(kwargs)
        return cls.objects.create(**data)