from django.contrib.auth.models import BaseUserManager
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from typing import Optional

class UserManager(BaseUserManager):
    """Custom user manager for creating users and superusers"""
    
    def create_user(
        self, 
        username: str, 
        email: Optional[str] = None, 
        password: Optional[str] = None, 
        **extra_fields
    ):
        """Create and save a regular user"""
        if not username:
            raise ValueError(_('The Username field must be set'))
        
        email = self.normalize_email(email) if email else None
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(
        self, 
        username: str, 
        email: Optional[str] = None, 
        password: Optional[str] = None, 
        **extra_fields
    ):
        """Create and save a superuser"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_verified', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        
        # Ensure superuser has all permissions via role
        if 'role' not in extra_fields:
            try:
                from .models import Role
                role = Role.objects.get_or_create_system_role()
                extra_fields['role'] = role
            except Exception:
                pass
        
        return self.create_user(username, email, password, **extra_fields)
    
    def get_by_natural_key(self, username):
        """Support Django's natural key serialization"""
        return self.get(username=username)