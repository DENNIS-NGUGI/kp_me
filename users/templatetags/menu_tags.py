# users/templatetags/menu_tags.py

from django import template
from django.urls import resolve

register = template.Library()


@register.simple_tag(takes_context=True)
def is_active_menu(context, url_name, app_name=None):
    """Check if a menu item is active"""
    request = context.get('request')
    if not request:
        return False
    
    # For admin URLs
    if url_name == '/admin/':
        return request.path.startswith('/admin/')
    
    # For external URLs
    if url_name.startswith('http'):
        return False
    
    try:
        # Get current URL info
        current_url = resolve(request.path_info)
        current_app = current_url.app_name or current_url.namespace
        current_url_name = current_url.url_name
        
        # Check if the current URL matches the menu item
        if app_name:
            return current_app == app_name and current_url_name == url_name
        
        # For URLs without app_name
        return current_url_name == url_name
    except:
        return False


@register.filter
def has_permission(user, perm):
    """Check if a user has a specific permission"""
    if not user or not user.is_authenticated:
        return False
    
    # Check for superuser
    if perm == 'is_superuser':
        return user.is_superuser
    
    # Check if the permission property exists and is True
    if hasattr(user, perm):
        value = getattr(user, perm)
        if callable(value):
            return value()
        return bool(value)
    
    # Check if it's a direct permission
    if hasattr(user, 'has_permission'):
        return user.has_permission(perm)
    
    return False


@register.filter
def has_any_permission(user, permissions):
    """Check if a user has any of the listed permissions"""
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    perm_list = [p.strip() for p in permissions.split(',')]
    for perm in perm_list:
        if has_permission(user, perm):
            return True
    return False


@register.filter
def has_all_permissions(user, permissions):
    """Check if a user has all of the listed permissions"""
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    perm_list = [p.strip() for p in permissions.split(',')]
    for perm in perm_list:
        if not has_permission(user, perm):
            return False
    return True