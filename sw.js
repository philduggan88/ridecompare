const CACHE = "ridecompare-v5";
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

// Cache-first for the app shell only; API calls (OneMap, OSRM) always go to network.
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin) return;
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request))
  );
});
