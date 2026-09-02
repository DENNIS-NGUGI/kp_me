from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
import logging

logger = logging.getLogger(__name__)

def permission_required(permission_codename, login_url=None, raise_exception=False):
    """
    Decorator for checking if a user has a specific permission.
    Uses database-stored permissions (NOT hardcoded).
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required(login_url=login_url)
        def _wrapped_view(request, *args, **kwargs):
            # Superusers bypass permission checks
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Check if user has the permission
            has_perm = request.user.has_permission(permission_codename)
            
            logger.debug(f"User {request.user.username} checking permission {permission_codename}: {has_perm}")
            
            if not has_perm:
                if raise_exception:
                    raise PermissionDenied
                messages.error(request, f"You don't have permission: {permission_codename}")
                return redirect('users:permission_denied')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def module_permission_required(module, action='view', login_url=None, raise_exception=False):
    """
    Decorator for checking module-level permissions.
    Handles both custom permissions (no model) and Django auto-generated permissions.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required(login_url=login_url)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Map module names to their permission names
            permission_mapping = {
                # Custom modules (no model) - use module name as-is
                'dashboard': f"{action}_dashboard",
                'reports': f"{action}_reports",
                
                # Model modules (Django auto-generated)
                'data_entry': f"{action}_dataentry",
                'indicators': f"{action}_indicator",
                'partners': f"{action}_partner",
                'projects': f"{action}_project",
                'users': f"{action}_user",
                'settings': f"{action}_systemsetting",
                'audit_log': f"{action}_auditlog",
                'county': f"{action}_county",
                'quarter': f"{action}_quarter",
                'thematic_area': f"{action}_thematicarea",
            }
            
            perm_codename = permission_mapping.get(module, f"{action}_{module}")
            has_perm = request.user.has_permission(perm_codename)
            
            logger.debug(f"User {request.user.username} checking module permission {module}/{action}: {has_perm} ({perm_codename})")
            
            if not has_perm:
                if raise_exception:
                    raise PermissionDenied
                messages.error(request, f"You don't have permission to {action} {module}")
                return redirect('users:permission_denied')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def admin_required(view_func):
    """Check if user has admin permissions using database permissions"""
    return permission_required('can_manage_users')(view_func)


def ncpd_or_admin_required(view_func):
    """
    Check if user is NCPD or Admin using database permissions
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        # Check if user has either permission
        if request.user.has_any_permission('can_approve_data', 'can_manage_users'):
            return view_func(request, *args, **kwargs)
        
        messages.error(request, "You don't have permission to access this page.")
        return redirect('users:permission_denied')
    
    return _wrapped_view


def view_reports_required(view_func):
    """Check if user can view reports using database permissions"""
    return permission_required('view_reports')(view_func)