from django import template
from django.contrib.auth import get_user_model

register = template.Library()
User = get_user_model()

@register.filter
def has_permission(user, permission_codename):
    """Check if user has a specific permission"""
    if not user or not user.is_authenticated:
        return False
    return user.has_permission(permission_codename)

@register.filter
def has_module_permission(user, module_action):
    """Check if user has module permission (format: 'module:action')"""
    if not user or not user.is_authenticated:
        return False
    try:
        module, action = module_action.split(':')
        return user.has_module_permission(module, action)
    except ValueError:
        return False

@register.filter
def user_role_name(user):
    """Get user's role name"""
    if not user or not user.is_authenticated:
        return 'No Role'
    if user.is_superuser:
        return 'admin'
    if user.role:
        return user.role.name
    return None

@register.filter
def user_role_display(user):
    """Get user's role display name"""
    if not user or not user.is_authenticated:
        return 'No Role Assigned'
    if user.is_superuser:
        return 'System Administrator'
    if user.role:
        return user.role.get_display_name()
    return 'No Role Assigned'

@register.filter
def user_can_approve(user):
    """Check if user can approve submissions"""
    if not user or not user.is_authenticated:
        return False
    return user.has_permission('can_approve_data')

@register.filter
def user_can_manage_users(user):
    """Check if user can manage users"""
    if not user or not user.is_authenticated:
        return False
    return user.has_permission('can_manage_users')

@register.filter
def user_can_manage_roles(user):
    """Check if user can manage roles"""
    if not user or not user.is_authenticated:
        return False
    return user.has_permission('can_manage_roles')

@register.simple_tag
def get_user_full_name(user):
    """Get user's full name"""
    if not user:
        return ''
    return user.get_full_name()