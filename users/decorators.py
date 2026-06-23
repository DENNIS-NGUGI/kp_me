from django.shortcuts import render
from django.contrib import messages
from functools import wraps

def role_required(allowed_roles=None, allowed_groups=None):
    """
    Decorator to check if user has the required role or permission.
    Shows a permission denied page instead of redirecting to login.
    """
    if allowed_roles is None:
        allowed_roles = []
    if allowed_groups is None:
        allowed_groups = []
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return render(request, 'errors/403.html', {
                    'error_message': 'Please login to access this resource.'
                }, status=403)
            
            # Check if user is superuser (bypass all checks)
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Check role
            if allowed_roles:
                user_role = request.user.role.name if request.user.role else None
                if user_role in allowed_roles:
                    return view_func(request, *args, **kwargs)
            
            # Check permission (if using Django permissions)
            if allowed_groups:
                for group in allowed_groups:
                    if request.user.groups.filter(name=group).exists():
                        return view_func(request, *args, **kwargs)
            
            # No permission - show 403 page
            return render(request, 'errors/403.html', {
                'error_message': 'You do not have permission to access this resource.'
            }, status=403)
        
        return wrapped
    return decorator


def admin_required(view_func):
    """Decorator for admin only access"""
    return role_required(allowed_roles=['admin'])(view_func)


def ncpd_or_admin_required(view_func):
    """Decorator for NCPD or admin access"""
    return role_required(allowed_roles=['admin', 'ncpd_me'])(view_func)


def ncpd_admin_or_county_required(view_func):
    """Decorator for NCPD, admin, or county access"""
    return role_required(allowed_roles=['admin', 'ncpd_me', 'county_me'])(view_func)


def view_reports_required(view_func):
    """Decorator for report viewing access"""
    return role_required(allowed_roles=['admin', 'ncpd_me', 'county_me', 'policy_maker'])(view_func)
