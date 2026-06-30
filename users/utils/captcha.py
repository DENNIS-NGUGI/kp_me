from captcha.models import CaptchaStore
from captcha.helpers import captcha_image_url
import logging

logger = logging.getLogger(__name__)

def validate_captcha(captcha_key, captcha_value):
    """
    Validate CAPTCHA
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not captcha_key or not captcha_value:
        return False, 'CAPTCHA is required.'
    
    try:
        stored_captcha = CaptchaStore.objects.get(hashkey=captcha_key)
        if stored_captcha.response.lower() != captcha_value.lower():
            return False, 'Invalid CAPTCHA. Please try again.'
        stored_captcha.delete()
        return True, ''
    except CaptchaStore.DoesNotExist:
        return False, 'Invalid CAPTCHA. Please try again.'
    except Exception as e:
        logger.error(f"CAPTCHA validation error: {e}")
        return False, 'CAPTCHA validation error. Please try again.'

def get_captcha_context():
    """Generate new CAPTCHA context for forms"""
    captcha_key = CaptchaStore.generate_key()
    return {
        'captcha_key': captcha_key,
        'captcha_image': captcha_image_url(captcha_key),
    }