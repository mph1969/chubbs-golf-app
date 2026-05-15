// Chubbs Golf — Service Worker
// Bump CACHE_VERSION on every deploy to trigger update prompt
const CACHE_VERSION = 'chubbs-v6.4';

// Cache API only supports GET requests on http(s) URLs. Trying to put POST
// requests or chrome-extension:// scripts throws TypeError noise into the
// console. This guard silences both.
function isCacheable(request){
  if(request.method !== 'GET') return false;
  try {
    const url = new URL(request.url);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch(e){ return false; }
}
const ASSETS = [
  './',
  './index.html',
  './cpi_manifest_v4.json',
  './ChubbsGatorIcon.png',
  './ChubbsGatorIcon.svg',
  './cpi_badge.svg',
  './mph_contact_qr.png',
  './mph_pay_code.jpeg',
  './nansha_logo.png',
  './dragonshot_icon.png',
  './dxgolf_icon.jpg',
  './CPI Handbook.pdf',
  './season-4.json'
];

// Install: cache all core assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_VERSION)
      .then(cache => cache.addAll(ASSETS))
      .then(() => self.skipWaiting())
  );
});

// Activate: delete old caches, claim clients
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_VERSION).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch: network-first for index.html (always check for updates), cache-first for assets
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // HTML pages: try network first, fall back to cache
  if (event.request.mode === 'navigate' || url.pathname.endsWith('.html') || url.pathname.endsWith('/')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          const clone = response.clone();
          if (isCacheable(event.request)) caches.open(CACHE_VERSION).then(cache => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // All other assets: cache-first, fallback to network
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(response => {
        const clone = response.clone();
        caches.open(CACHE_VERSION).then(cache => cache.put(event.request, clone));
        return response;
      });
    })
  );
});

// Listen for skip-waiting message from the app
self.addEventListener('message', event => {
  if (event.data === 'skipWaiting') self.skipWaiting();
});
