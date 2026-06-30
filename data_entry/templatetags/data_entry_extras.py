# data_entry/templatetags/data_entry_extras.py

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    if dictionary is None:
        return ''
    return dictionary.get(key, '')

@register.filter
def get_indicator_value(dictionary, indicator_id):
    """Get value for a specific indicator from the values dictionary"""
    if dictionary is None:
        return ''
    key = f'indicator_{indicator_id}'
    return dictionary.get(key, '')

@register.filter
def in_list(value, arg):
    """Check if value is in a comma-separated list"""
    if not value:
        return False
    return value in arg.split(',')