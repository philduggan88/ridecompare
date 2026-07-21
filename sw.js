const CACHE = "ridecompare-v12";
const ASSETS = [
  "./", "./index.html", "./manifest.json", "./icon.svg",
  "./icons/grab.png", "./icons/gojek.png", "./icons/tada.png",
  "./icons/ryde.png", "./icons/zig.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// App shell only; API calls (OneMap, OSRM) always go to network. Serve from
// cache, refresh in the background so updates arrive without a CACHE bump.
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin || e.request.method !== "GET") return;
  e.respondWith(
    caches.match(e.request).then((hit) => {
      const refetch = fetch(e.request)
        .then((res) => {
          if (res.ok) e.waitUntil(caches.open(CACHE).then((c) => c.put(e.request, res.clone())));
          return res;
        })
        .catch(() => hit);
      // Background refresh must be tied to the event lifetime, or the SW may
      // be killed after responding from cache and the update silently lost.
      if (hit) e.waitUntil(refetch);
      return hit || refetch;
    })
  );
});
