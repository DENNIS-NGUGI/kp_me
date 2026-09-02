"""
Centralized permission checking for all models
All permission logic lives here - DRY principle
"""

from django.db.models import Q


# ============================================================
# DATA ENTRY PERMISSIONS (Using Django auto-generated permissions)
# ============================================================

def can_view_data_entry(user, entry):
    """Check if user can view a data entry"""
    if user.is_superuser:
        return True
    
    if not user.has_permission('view_dataentry'):
        return False
    
    # County users can only view their county's data
    if user.is_county_user and user.county == entry.county:
        return True
    
    # NCPD/Admin can view all
    if user.has_permission('can_approve_data'):
        return True
    
    return False


def can_edit_data_entry(user, entry):
    """Check if user can edit a data entry"""
    # Approved and Submitted entries cannot be edited
    if entry.status in ['approved', 'submitted']:
        return False
    
    if entry.is_locked:
        return False
    
    if user.is_superuser:
        return True
    
    if not user.has_permission('change_dataentry'):
        return False
    
    # County users can only edit their county's data
    if user.is_county_user and user.county == entry.county:
        return entry.status in ['draft', 'rejected']
    
    # NCPD/Admin can edit all
    if user.has_permission('can_approve_data'):
        return True
    
    return False


def can_submit_data_entry(user, entry):
    """Check if user can submit a data entry"""
    if entry.status == 'approved':
        return False
    
    if entry.is_locked:
        return False
    
    if user.is_superuser:
        return True
    
    if not user.has_permission('add_dataentry'):
        return False
    
    # County users can only submit their county's data
    if user.is_county_user and user.county == entry.county:
        return entry.status in ['draft', 'rejected']
    
    # NCPD/Admin can submit all
    if user.has_permission('can_approve_data'):
        return True
    
    return False


def can_approve_data_entry(user, entry):
    """Check if user can approve a data entry"""
    if entry.status != 'submitted':
        return False
    
    if user.is_superuser:
        return True
    
    if not user.has_permission('can_approve_data'):
        return False
    
    # County users can only approve their county's data
    if user.is_county_user and user.county == entry.county:
        return True
    
    # NCPD/Admin can approve all
    return True


def can_delete_data_entry(user, entry):
    """Check if user can delete a data entry"""
    if entry.status in ['approved', 'submitted']:
        return False
    
    if user.is_superuser:
        return True
    
    if not user.has_permission('delete_dataentry'):
        return False
    
    # County users can only delete their county's data
    if user.is_county_user and user.county == entry.county:
        return entry.status in ['draft', 'rejected']
    
    # NCPD/Admin can delete all
    if user.has_permission('can_approve_data'):
        return True
    
    return False


def get_data_entry_queryset_filter(user):
    """
    Get the filter for data entry querysets based on user permissions
    Returns: Q object
    """
    if user.is_superuser:
        return Q()
    
    if user.is_county_user and user.county:
        return Q(county=user.county)
    
    if user.has_permission('can_approve_data'):
        return Q()
    
    # No access - return empty queryset
    return Q(pk__in=[])


def get_user_data_scope(user):
    """
    Get the data scope for a user
    Returns: 'county', 'national', or 'none'
    """
    if user.is_superuser:
        return 'national'
    
    if user.is_county_user:
        return 'county'
    
    if user.has_permission('can_approve_data'):
        return 'national'
    
    return 'none'


# ============================================================
# PARTNER PERMISSIONS (Using Django auto-generated)
# ============================================================

def can_view_partners(user):
    """Check if user can view partners"""
    if user.is_superuser:
        return True
    
    if user.has_permission('view_partner'):
        return True
    
    return False


def can_manage_partners(user):
    """Check if user can manage partners"""
    if user.is_superuser:
        return True
    
    if user.has_permission('can_manage_partners'):
        return True
    
    return False


# ============================================================
# PROJECT PERMISSIONS (Using Django auto-generated)
# ============================================================

def can_view_projects(user):
    """Check if user can view projects"""
    if user.is_superuser:
        return True
    
    if user.has_permission('view_project'):
        return True
    
    return False


def can_manage_projects(user):
    """Check if user can manage projects"""
    if user.is_superuser:
        return True
    
    if user.has_permission('can_manage_projects'):
        return True
    
    return False


def get_partner_queryset_filter(user):
    """
    Get the filter for partner querysets based on user permissions
    Returns: Q object
    """
    if user.is_superuser:
        return Q()
    
    if user.is_county_user:
        return Q(counties=user.county)
    
    if user.has_permission('can_approve_data') or user.has_permission('can_manage_partners'):
        return Q()
    
    # Partner users can only see their own partner
    if user.role and user.role.name == 'partner':
        return Q(users=user)
    
    # No access
    return Q(pk__in=[])


def get_project_queryset_filter(user):
    """
    Get the filter for project querysets based on user permissions
    Returns: Q object
    """
    if user.is_superuser:
        return Q()
    
    if user.is_county_user:
        return Q(counties=user.county)
    
    if user.has_permission('can_approve_data') or user.has_permission('can_manage_projects'):
        return Q()
    
    # Partner users can only see their partner's projects
    if user.role and user.role.name == 'partner':
        partner_ids = user.partners.values_list('id', flat=True)
        return Q(partner__in=partner_ids)
    
    # No access
    return Q(pk__in=[])