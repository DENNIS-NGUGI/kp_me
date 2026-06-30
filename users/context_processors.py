from django.urls import resolve
from django.utils.translation import gettext_lazy as _
from data_entry.models import DataEntry

def menu_items(request):
    """Context processor providing dynamic menu items based on permissions"""
    
    if not request.user.is_authenticated or not request.user.is_verified:
        return {'menu_items': [], 'pending_count': 0}
    
    user = request.user
    menu_items = []
    
    # ===== MAIN SECTION =====
    main_items = []
    if user.can_view_dashboard:
        main_items.append({
            'name': 'Dashboard',
            'icon': 'bi-speedometer2',
            'url': 'reports:dashboard',
            'permissions': ['view_dashboard'],
            'app_name': 'reports',
        })
    
    if main_items:
        menu_items.append({'label': 'Main', 'items': main_items})
    
    # ===== DATA MANAGEMENT SECTION =====
    data_items = []
    
    if user.can_view_data_entry or user.can_add_data_entry:
        data_items.append({
            'name': 'Data Entry',
            'icon': 'bi-pencil-square',
            'url': 'data_entry:list',
            'permissions': ['view_dataentry', 'add_dataentry'],
            'app_name': 'data_entry',
        })
    
    if user.can_view_indicators:
        data_items.append({
            'name': 'Indicators',
            'icon': 'bi-list-ul',
            'url': 'indicators:list',
            'permissions': ['view_indicator'],
            'app_name': 'indicators',
        })
    
    if data_items:
        menu_items.append({'label': 'Data Management', 'items': data_items})
    
    # ===== REPORTS SECTION =====
    if user.can_view_reports:
        report_items = [{
            'name': 'Reports',
            'icon': 'bi-file-earmark-text',
            'url': 'reports:report_list',
            'permissions': ['view_reports'],
            'app_name': 'reports',
        }]
        
        if user.can_approve_data:
            report_items.append({
                'name': 'Pending Approvals',
                'icon': 'bi-clock-history',
                'url': 'reports:pending_reports',
                'permissions': ['can_approve_data'],
                'app_name': 'reports',
                'badge': True,
            })
        
        if user.can_export_reports:
            report_items.append({
                'name': 'Export/Import',
                'icon': 'bi-arrow-up-down',
                'url': 'reports:export_data',
                'permissions': ['export_reports'],
                'app_name': 'reports',
            })
        
        menu_items.append({'label': 'Reports', 'items': report_items})
    
    # ===== PARTNERS SECTION =====
    if user.can_view_partners or user.can_manage_partners:
        partner_items = []
        
        if user.can_view_partners:
            partner_items.append({
                'name': 'Partners',
                'icon': 'bi-buildings',
                'url': 'partners:list',
                'permissions': ['view_partner'],
                'app_name': 'partners',
            })
        
        if user.can_manage_partners:
            partner_items.append({
                'name': 'Add Partner',
                'icon': 'bi-plus-circle',
                'url': 'partners:add',
                'permissions': ['can_manage_partners'],
                'app_name': 'partners',
            })
        
        if partner_items:
            menu_items.append({'label': 'Partners', 'items': partner_items})
    
    # ===== PROJECTS SECTION =====
    if user.can_view_projects or user.can_manage_projects:
        project_items = []
        
        if user.can_view_projects:
            project_items.append({
                'name': 'Projects',
                'icon': 'bi-folder',
                'url': 'partners:project_list',
                'permissions': ['view_project'],
                'app_name': 'partners',
            })
        
        if user.can_manage_projects:
            project_items.append({
                'name': 'Add Project',
                'icon': 'bi-plus-circle',
                'url': 'partners:project_add',
                'permissions': ['can_manage_projects'],
                'app_name': 'partners',
            })
        
        if project_items:
            menu_items.append({'label': 'Projects', 'items': project_items})
    
    # ===== PARTNER DASHBOARD =====
    if user.can_view_partners and user.can_view_dashboard:
        menu_items.append({
            'label': 'Partner Dashboard',
            'items': [{
                'name': 'Partner Dashboard',
                'icon': 'bi-speedometer2',
                'url': 'partners:dashboard',
                'permissions': ['view_partner'],
                'app_name': 'partners',
            }]
        })
    
    # ===== ADMINISTRATION SECTION =====
    # Show if user has ANY administration permission
    if (user.can_manage_roles or user.can_manage_users or 
        user.can_manage_system_settings or user.can_view_audit_log or
        user.can_view_users):  
        admin_items = []
        
        # Roles - only if can manage
        if user.can_manage_roles:
            admin_items.append({
                'name': 'Roles',
                'icon': 'bi-shield-lock',
                'url': 'users:role_list',
                'permissions': ['can_manage_roles'],
                'app_name': 'users',
            })
        
        # Users - show if can view OR manage
        if user.can_view_users or user.can_manage_users:
            admin_items.append({
                'name': 'Users',
                'icon': 'bi-people',
                'url': 'users:user_management',
                'permissions': ['view_user', 'can_manage_users'],
                'app_name': 'users',
            })
        
        # Counties - system settings
        if user.can_manage_system_settings:
            admin_items.append({
                'name': 'Counties',
                'icon': 'bi-geo-alt',
                'url': 'settings:counties',
                'permissions': ['can_manage_system_settings'],
                'app_name': 'settings',
            })
        
        # Quarters - system settings
        if user.can_manage_system_settings:
            admin_items.append({
                'name': 'Quarters',
                'icon': 'bi-calendar3',
                'url': 'settings:quarters',
                'permissions': ['can_manage_system_settings'],
                'app_name': 'settings',
            })
        
        # System Settings
        if user.can_manage_system_settings:
            admin_items.append({
                'name': 'System Settings',
                'icon': 'bi-gear',
                'url': 'settings:index',
                'permissions': ['can_manage_system_settings'],
                'app_name': 'settings',
            })
        
        # Audit Log - show if user has view_auditlog permission
        if user.can_view_audit_log:
            admin_items.append({
                'name': 'Audit Log',
                'icon': 'bi-clock-history',
                'url': 'settings:audit_log',
                'permissions': ['view_auditlog'],
                'app_name': 'settings',
            })
        
        # Django Admin - superuser only
        if user.is_superuser:
            admin_items.append({
                'name': 'Django Admin',
                'icon': 'bi-database-gear',
                'url': '/admin/',
                'permissions': ['is_superuser'],
                'app_name': 'admin',
                'external': True,
            })
        
        if admin_items:
            menu_items.append({'label': 'Administration', 'items': admin_items})
    
    return {
        'menu_items': menu_items,
        'pending_count': get_pending_count(request),
    }

def get_pending_count(request):
    """Get pending approvals count"""
    if not request.user.is_authenticated or not request.user.is_verified:
        return 0
    
    if request.user.is_superuser or request.user.has_permission('can_approve_data'):
        if request.user.is_county_user:
            return DataEntry.objects.filter(
                county=request.user.county, 
                status='submitted'
            ).count()
        return DataEntry.objects.filter(status='submitted').count()
    
    return 0
