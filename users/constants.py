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