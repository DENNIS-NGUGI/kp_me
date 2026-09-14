const CACHE_NAME = 'kppimes-static-v1';

self.addEventListener('install', () => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
    const requestUrl = new URL(event.request.url);
    if (event.request.method !== 'GET' || requestUrl.origin !== self.location.origin || !requestUrl.pathname.startsWith('/static/')) {
        return;
    }

    event.respondWith(
        caches.open(CACHE_NAME).then((cache) =>
            cache.match(event.request).then((cachedResponse) => {
                const networkResponse = fetch(event.request).then((response) => {
                    if (response.ok) cache.put(event.request, response.clone());
                    return response;
                });
                return cachedResponse || networkResponse;
            })
        )
    );
});