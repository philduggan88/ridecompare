# RideCompare

**Live at https://philduggan88.github.io/ridecompare/** (GitHub Pages —
works anywhere, HTTPS, so clipboard copy and the offline service worker are
active). Pushing to `main` redeploys automatically.

One search instead of five apps: enter pickup + destination once, see estimated
fares for **Grab, Gojek, TADA, Ryde and Zig** side by side, then tap **Open** to
jump straight into the app you pick.

## Why estimates, not live prices?

None of the five operators expose a public fare-quote API, so live surge prices
can't be pulled by a third-party app. RideCompare instead:

1. Geocodes both addresses with **OneMap** (Singapore government, free, no key).
2. Gets real driving distance/time from the public **OSRM** router
   (padded ×1.35 for SG traffic).
3. Applies each operator's published fare structure
   (base + per-km + per-min + platform fee) and shows a −15%/+25% range.

The ranking is the useful part — it tells you which one or two apps are worth
opening for a real quote. Fare tables live in the `SERVICES` array at the top
of the script in `index.html` (last reviewed Jul 2026); edit there when
operators revise pricing.

## Opening the apps

- **Grab** — deep link with pickup + destination pre-filled
  (`grab://open?screenType=BOOKING&…`).
- **Gojek / TADA / Ryde / Zig** — no public deep-link parameters, so the app is
  opened directly and your destination is **copied to the clipboard** for a
  one-tap paste. If an app isn't installed the button falls back to its
  App Store / web page after ~2s.

## Run it

The server runs automatically via a LaunchAgent
(`~/Library/LaunchAgents/com.philipduggan.ridecompare.plist`) — it starts at
login and restarts if it dies, so there is nothing to launch manually.
Logs: `/tmp/ridecompare.log`. To stop it:

```sh
launchctl bootout gui/$(id -u)/com.philipduggan.ridecompare
```

On your iPhone (same Wi-Fi / hotspot as the Mac), open
**http://philips-macbook-air.local:4880** in Safari → Share →
**Add to Home Screen**. The `.local` (Bonjour) name keeps working when the
Mac's IP changes between networks — prefer it over a raw IP.

`start.sh` remains as a manual fallback for running the server ad-hoc
(it will fail with "Address already in use" while the LaunchAgent is running).

Notes for phone use over plain HTTP: clipboard copy may be blocked outside a
secure context (the deep links still work), and the service worker
(offline shell) only activates over HTTPS. For access away from home Wi-Fi,
the app is fully static — host the folder on GitHub Pages or a Tailscale
HTTPS endpoint and everything (including clipboard + offline) works.

## Files

- `index.html` — the whole app (UI + fare model + deep links), no build step
- `manifest.json`, `sw.js`, `icon.svg`, `apple-touch-icon.png` — PWA bits
- `start.sh` — LAN server on port 4880
