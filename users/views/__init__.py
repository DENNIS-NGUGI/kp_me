from .auth import (
    login_view,
    logout_view,
    register,
    verify_otp,
    resend_otp,
    terms_conditions,
    ajax_captcha_refresh,
)
from .profile import (
    profile,
    edit_profile,
    permission_denied,
)
from .user_management import (
    user_management,
    user_edit,
    user_toggle_status,
    user_delete,
    user_bulk_action,
)
from .role_management import (
    role_list,
    role_add,
    role_edit,
    role_delete,
    role_update_permissions,
    role_clone,  # Make sure this is imported
)

__all__ = [
    # Auth views
    'login_view',
    'logout_view',
    'register',
    'verify_otp',
    'resend_otp',
    'terms_conditions'
    'ajax_captcha_refresh',
    
    # Profile views
    'profile',
    'edit_profile',
    'permission_denied',
    
    # User management views
    'user_management',
    'user_edit',
    'user_toggle_status',
    'user_delete',
    'user_bulk_action',
    
    # Role management views
    'role_list',
    'role_add',
    'role_edit',
    'role_delete',
    'role_update_permissions',
    'role_clone',
]