// ========== VERSION CONTROL ==========
const VERSION = '2.4';
const CACHE_NAME = `company-workflow-v${VERSION}`;
const OFFLINE_URL = '/offline';

// ========== INSTALL - Cache offline page ==========
self.addEventListener('install', event => {
  console.log(`[SW v${VERSION}] Installing...`);

  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('[SW] Caching offline page');
      return cache.addAll([
        OFFLINE_URL,
        '/static/images/logo.png'
      ]);
    })
  );

  self.skipWaiting();
});

// ========== ACTIVATE - Cleanup old caches ==========
self.addEventListener('activate', event => {
  console.log(`[SW v${VERSION}] Activating...`);

  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames
          .filter(cacheName => cacheName.startsWith('company-workflow-v'))
          .filter(cacheName => cacheName !== CACHE_NAME)
          .map(cacheName => {
            console.log('[SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          })
      );
    })
  );

  event.waitUntil(clients.claim());
});

// ========== FETCH - Offline fallback ==========
self.addEventListener('fetch', event => {
  // Chỉ xử lý navigation requests (HTML pages)
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .catch(() => {
          console.log('[SW] Network failed, serving offline page');
          return caches.match(OFFLINE_URL);
        })
    );
  } else {
    // Các request khác (CSS, JS, images) - fetch bình thường
    event.respondWith(
      fetch(event.request).catch(err => {
        console.log('[SW] Resource fetch failed:', event.request.url);
        // Không trả về gì, browser sẽ xử lý
        throw err;
      })
    );
  }
});

// ========== MESSAGE - Communicate với client ==========
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});