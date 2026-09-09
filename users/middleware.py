from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """Restrict temporary-password accounts to changing their password."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        allowed_paths = {
            reverse('users:change_password'),
            reverse('users:logout'),
        }
        if (
            user.is_authenticated
            and user.force_password_change
            and request.path not in allowed_paths
        ):
            return redirect('users:change_password')
        return self.get_response(request)