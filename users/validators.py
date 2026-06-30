import re
from typing import List

from .constants import AuthConstants

def validate_password_strength(password: str) -> List[str]:
    """
    Validate password strength
    
    Args:
        password: Password to validate
    
    Returns:
        List of error messages, empty if valid
    """
    errors = []
    
    if len(password) < AuthConstants.PASSWORD_MIN_LENGTH:
        errors.append(f'Password must be at least {AuthConstants.PASSWORD_MIN_LENGTH} characters.')
    
    if not any(c.isdigit() for c in password):
        errors.append('Password must contain at least one number.')
    
    if not any(c.isupper() for c in password):
        errors.append('Password must contain at least one uppercase letter.')
    
    if not any(c.islower() for c in password):
        errors.append('Password must contain at least one lowercase letter.')
    
    # Check for common passwords
    if password.lower() in AuthConstants.COMMON_PASSWORDS:
        errors.append('Password is too common. Please choose a stronger password.')
    
    return errors

def validate_phone_number(phone: str) -> bool:
    """Validate phone number format"""
    return bool(re.match(AuthConstants.PHONE_REGEX, phone))

def validate_username(username: str) -> bool:
    """Validate username format"""
    return bool(re.match(AuthConstants.USERNAME_REGEX, username))