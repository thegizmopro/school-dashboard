// Harmony Today service worker — offline shell + last-good data.
//
// Strategy:
//   documents (/, board, budget, install)  network-first  -> deploys land without waiting for a SW bump
//   site data (JSON, ICS)                  network-first  -> fresh when online, last-good when offline
//   icons + fonts                          cache-first
//
// Cache KEYS strip the "?t=" cache-bust query the page adds, so every render
// reuses one entry per file instead of accumulating unique URLs.
// Bump VERSION when changing the precache SHELL list.
const VERSION = 'v-2026-09-26';
const SHELL = ['/', '/board.html', '/budget.html', '/install.html', '/manifest.webmanifest',
               '/apple-touch-icon.png', '/favicon.png', '/icon-192.png', '/icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

const keyFor = req => {
  const u = new URL(req.url);
  return new Request(u.origin + u.pathname);   // drop ?t= cache-bust
};

async function netFirst(req, key) {
  try {
    const fresh = await fetch(req);
    if (fresh && fresh.ok) {
      const c = await caches.open(VERSION);
      c.put(key, fresh.clone());
    }
    return fresh;
  } catch (offline) {
    const hit = await caches.match(key);
    if (hit) return hit;
    if (req.mode === 'navigate') {
      const shell = await caches.match('/');   // never show a raw offline error on the tablet
      if (shell) return shell;
    }
    throw offline;
  }
}

async function cacheFirst(req, key) {
  const hit = await caches.match(key);
  if (hit) return hit;
  const fresh = await fetch(req);
  if (fresh && fresh.ok) {
    const c = await caches.open(VERSION);
    c.put(key, fresh.clone());
  }
  return fresh;
}

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  if (url.origin === location.origin) {
    const isData = url.pathname.startsWith('/data/') || url.pathname.endsWith('.json') || url.pathname.endsWith('.ics');
    const isDoc = req.mode === 'navigate' || url.pathname === '/' || url.pathname.endsWith('.html');
    if (isDoc || isData) {
      e.respondWith(netFirst(req, keyFor(req)));
      return;
    }
    e.respondWith(cacheFirst(req, keyFor(req)));   // icons, manifest, images
    return;
  }

  // cross-origin: weather API (last-good) + Google Fonts (cache-first)
  if (url.hostname === 'api.open-meteo.com') {
    e.respondWith(netFirst(req, keyFor(req)));
  } else if (/fonts\.(googleapis|gstatic)\.com$/.test(url.hostname)) {
    e.respondWith(cacheFirst(req, keyFor(req)));
  }
  // everything else cross-origin: untouched, straight to network
});
