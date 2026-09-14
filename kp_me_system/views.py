from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import JsonResponse
from django.shortcuts import render

def handler403(request, exception):
    return render(request, 'errors/403.html', status=403)

def handler404(request, exception):
    return render(request, 'errors/404.html', status=404)

def handler500(request):
    return render(request, 'errors/500.html', status=500)


def web_manifest(request):
    """Serve the install manifest with deployment-safe static asset URLs."""
    return JsonResponse({
        'name': 'Kenya Population Programme M&E System',
        'short_name': 'KPPIMES',
        'start_url': '/',
        'display': 'standalone',
        'background_color': '#f5f7f5',
        'theme_color': '#1a5632',
        'icons': [
            {
                'src': staticfiles_storage.url('images/pwa-icon-192.png'),
                'sizes': '192x192',
                'type': 'image/png',
                'purpose': 'any maskable',
            },
            {
                'src': staticfiles_storage.url('images/pwa-icon-512.png'),
                'sizes': '512x512',
                'type': 'image/png',
                'purpose': 'any maskable',
            },
        ],
    }, content_type='application/manifest+json')


def service_worker(request):
    """Serve the worker from the root so it can control the entire application."""
    response = render(request, 'service-worker.js', content_type='application/javascript')
    response['Cache-Control'] = 'no-cache'
    response['Service-Worker-Allowed'] = '/'
    return response
