from datetime import timedelta

class AuthConstants:
    """Centralized constants for authentication and authorization"""
    
    # Login attempt limits
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=30)
    
    # OTP settings
    OTP_LENGTH = 6
    OTP_EXPIRY_MINUTES = 10
    OTP_MAX_ATTEMPTS = 3
    OTP_RESEND_COOLDOWN = 60  # seconds
    
    # Password requirements
    PASSWORD_MIN_LENGTH = 8
    
    # Validation patterns
    PHONE_REGEX = r'^\+?1?\d{9,15}$'
    USERNAME_REGEX = r'^[\w-]+$'
    
    # Common weak passwords for validation
    COMMON_PASSWORDS = [
        'password', '12345678', 'qwerty123', 'admin123',
        'password123', '123456789', 'letmein', 'welcome'
    ]
    
    # Cache timeouts
    ROLE_CACHE_TIMEOUT = 3600  # 1 hour
    PERMISSION_CACHE_TIMEOUT = 3600  # 1 hour
    
    # Audit log retention
    AUDIT_LOG_RETENTION_DAYS = 90


class RoleConstants:
    """Role-related constants"""
    
    # System roles that cannot be deleted or modified
    SYSTEM_ROLES = ['admin', 'superuser', 'system']
    
    # Default system role priorities
    SYSTEM_ADMIN_PRIORITY = 100
    DEFAULT_ADMIN_PRIORITY = 90
    MANAGER_PRIORITY = 50
    USER_PRIORITY = 10
    
    # Minimum permissions required for system roles
    SYSTEM_ROLE_REQUIRED_PERMISSIONS = [
        'view_dashboard',
        'view_dataentry',
        'view_indicator',
        'view_user',
    ]
    
    # Role-to-model permission mapping
    # Maps module names to Django's auto-generated permission model names
    MODEL_PERMISSION_MAPPING = {
        # Modules with models (Django auto-generates: action_modelname)
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
    }