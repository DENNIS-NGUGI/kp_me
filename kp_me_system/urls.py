from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.shortcuts import render
from users.views import ajax_captcha_refresh 
from .views import handler403, handler404, handler500

# Custom error handlers
def handler403(request, exception):
    return render(request, 'errors/403.html', status=403)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('captcha/refresh/', ajax_captcha_refresh, name='captcha-refresh'),  
    path('captcha/', include('captcha.urls')), 
    path('', include('public.urls')),
    path('users/', include('users.urls')),
    path('indicators/', include('indicators.urls')),
    path('data/', include('data_entry.urls')),
    path('reports/', include('reports.urls')),
    path('notifications/', include('notifications.urls')),
    path('partners/', include('partners.urls')),
    path('settings/', include('settings.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Error handlers
handler403 = handler403
handler404 = handler404
handler500 = handler500