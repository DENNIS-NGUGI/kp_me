from .email import send_otp_email
from .captcha import validate_captcha, get_captcha_context

# For backwards compatibility with templatetags
def user_has_permission(user, module, action):
    """Check if user has permission for a module action"""
    if user.is_superuser:
        return True
    if not user.role:
        return False
    perm_codename = f"{action}_{module}"
    return user.role.permissions.filter(codename=perm_codename).exists()

def get_user_role_name(user):
    """Get the role name as a string for compatibility"""
    if user.is_superuser:
        return 'admin'
    if user.role:
        return user.role.name
    return None

def get_user_role_display(user):
    """Get the role display name"""
    if user.is_superuser:
        return 'System Administrator'
    if user.role:
        return user.role.get_display_name()
    return 'No Role Assigned'

def user_can_approve(user):
    """Check if user can approve submissions"""
    if user.is_superuser:
        return True
    if user.role:
        return user.role.permissions.filter(codename='can_approve_data').exists()
    return False

def user_can_manage_users(user):
    """Check if user can manage users"""
    if user.is_superuser:
        return True
    if user.role:
        return user.role.permissions.filter(codename='can_manage_users').exists()
    return False

__all__ = [
    'send_otp_email',
    'validate_captcha',
    'get_captcha_context',
    'user_has_permission',
    'get_user_role_name',
    'get_user_role_display',
    'user_can_approve',
    'user_can_manage_users',
]