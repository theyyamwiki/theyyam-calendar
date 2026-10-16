// ⚠️ സൈറ്റിൽ (index.html) മാറ്റം വരുത്തുമ്പോൾ ഈ നമ്പർ ഒന്ന് കൂട്ടിയാൽ മൊബൈലിലെ പഴയ ഫയലുകൾ മായ്ച്ച് പുതിയത് എടുക്കും.
const CACHE_NAME = 'theyyam-cache-v2';

const APP_SHELL = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png'
];

self.addEventListener('install', (e) => {
  console.log('Service Worker Installed');
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// വിജയകരമായ മറുപടി മാത്രം കാഷെ ചെയ്യുന്നു (404 / പിഴവ് പേജുകൾ സൂക്ഷിക്കില്ല)
function putInCache(key, res) {
  if (res && (res.ok || res.type === 'opaque')) {
    const clone = res.clone();
    caches.open(CACHE_NAME).then((cache) => cache.put(key, clone));
  }
  return res;
}

// ആദ്യം നെറ്റ്‌വർക്ക്; ഓഫ്‌ലൈൻ ആണെങ്കിൽ മാത്രം കാഷെ.
// key = ?query ഇല്ലാത്ത ലിങ്ക് (?lang=hi, ?date=..., ?t=... കൊണ്ട് കാഷെ നിറയാതിരിക്കാൻ)
function networkFirst(request, key, fallbackUrl) {
  return fetch(request)
    .then((res) => putInCache(key, res))
    .catch(() =>
      caches.match(key).then((cached) => cached || (fallbackUrl ? caches.match(fallbackUrl) : undefined))
    );
}

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;

  const url = new URL(e.request.url);
  const key = url.origin + url.pathname;

  // CSV ഫയലുകൾ (data.csv, year_mapping.csv ...) — എപ്പോഴും പുതിയത്; ഓഫ്‌ലൈൻ ആണെങ്കിൽ മാത്രം കാഷെ.
  if (url.pathname.endsWith('.csv')) {
    e.respondWith(networkFirst(e.request, key));
    return;
  }

  // പേജ് (index.html, കാവ് പേജുകൾ) — എപ്പോഴും പുതിയത്, അതിനാൽ സൈറ്റ് മാറ്റിയാൽ ഉടൻ ലഭിക്കും.
  if (e.request.mode === 'navigate' || url.pathname === '/' || url.pathname.endsWith('.html')) {
    e.respondWith(networkFirst(e.request, key, '/index.html'));
    return;
  }

  // ബാക്കി (ഐക്കൺ, ഫോണ്ട്, ചിത്രങ്ങൾ): ആദ്യം കാഷെ, ഇല്ലെങ്കിൽ നെറ്റ്‌വർക്ക്.
  e.respondWith(
    caches.match(e.request).then((cached) => {
      return (
        cached ||
        fetch(e.request).then((res) => putInCache(e.request, res))
      );
    })
  );
});
