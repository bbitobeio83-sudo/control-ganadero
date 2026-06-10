const CACHE = 'ganadero-v1';

const PRECACHE = [
  '/offline',
  '/static/css/style.css',
];

// ── Install: pre-cache páginas y assets críticos ──
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: eliminar caches viejos ──
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== CACHE).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// ── Fetch ──
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Solo GET
  if (request.method !== 'GET') return;

  // CDN (Bootstrap, Chart.js) y archivos estáticos: cache-first
  if (url.hostname === 'cdn.jsdelivr.net' || url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then(cached => {
        if (cached) return cached;
        return fetch(request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE).then(c => c.put(request, clone));
          }
          return response;
        }).catch(() => cached || new Response('', { status: 503 }));
      })
    );
    return;
  }

  // Páginas de navegación: network-first con fallback offline
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() =>
        caches.match('/offline')
          .then(r => r || new Response('<h1>Sin conexión</h1>', {
            status: 503,
            headers: { 'Content-Type': 'text/html; charset=utf-8' }
          }))
      )
    );
    return;
  }
});
