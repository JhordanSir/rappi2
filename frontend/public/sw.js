// Service worker mínimo para que la app sea instalable (PWA) y tenga un
// offline básico del shell. No intercepta el API ni recursos de terceros.
const CACHE = "rappi2-shell-v1";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  // Solo gestionamos peticiones del propio origen (el shell); el API y los mapas
  // pasan directo a la red.
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    fetch(req)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      })
      .catch(() => caches.match(req).then((m) => m || caches.match("/"))),
  );
});
