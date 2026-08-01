/*
 * Connectify service worker - just enough for the app to install as a
 * desktop PWA and open instantly.
 *
 * Static assets are cached as they are fetched (they carry content hashes,
 * so staleness is impossible); everything else - the app shell and every
 * /api call - goes to the network. The server is on localhost, so there is
 * no offline story to fake: without the server the app cannot do anything
 * anyway, and pretending otherwise would just hide real failures.
 */
const CACHE = 'connectify-static-v1';

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key !== CACHE) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  const isHashedAsset = url.origin === self.location.origin
    && url.pathname.startsWith('/static/assets/');
  if (!isHashedAsset) return;   // network for the shell and the API

  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const hit = await cache.match(event.request);
    if (hit) return hit;
    const response = await fetch(event.request);
    if (response.ok) cache.put(event.request, response.clone());
    return response;
  })());
});
