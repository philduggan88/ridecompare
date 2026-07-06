#!/usr/bin/env python3
"""Fit per-service calibration factors for RideCompare from real receipts.

Replicates the app's fare model (index.html SERVICES + fareContext), routes
each receipt's from/to via OneMap + OSRM the same way the app does, and fits
factor = median(actual / modelled) per service, spread from the residuals.
"""
import json, math, ssl, sys, time, urllib.parse, urllib.request
from datetime import datetime
from statistics import median

CTX = ssl.create_default_context()
import os
SCRATCH = os.path.join(os.path.dirname(__file__), "..", "data")  # rides.json in, calibration.json out

SERVICES = {
    "grab":  dict(base=3.20, perKm=0.75, perMin=0.25, fee=0.90),
    "gojek": dict(base=2.90, perKm=0.70, perMin=0.24, fee=1.40),
    "tada":  dict(base=2.80, perKm=0.68, perMin=0.22, fee=0.70),
    "ryde":  dict(base=2.90, perKm=0.70, perMin=0.22, fee=0.80),
}
CHANGI = (1.3644, 103.9915)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ridecompare-calibration/1.0"})
    with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
        return json.load(r)

GEO_CACHE = {}
def onemap(q):
    url = ("https://www.onemap.gov.sg/api/common/elastic/search?searchVal="
           + urllib.parse.quote(q) + "&returnGeom=Y&getAddrDetails=Y&pageNum=1")
    try:
        res = fetch(url).get("results") or []
        return (float(res[0]["LATITUDE"]), float(res[0]["LONGITUDE"])) if res else None
    except Exception:
        return None

import re
def geocode(q):
    if q in GEO_CACHE: return GEO_CACHE[q]
    out = None
    # 1) postal code is the most reliable key: "(S)597630" or "Singapore 129117"
    m = re.search(r"\(S\)\s*(\d{6})|Singapore\s+(\d{6})|\b(\d{6})\b", q)
    if m:
        out = onemap(next(g for g in m.groups() if g))
        time.sleep(0.3)
    # 2) full string, 3) progressively simplified chunks
    if not out:
        candidates = [q, q.split(",")[0].strip()]
        m2 = re.search(r"\d+[A-Za-z]?\s+[A-Za-z' ]+(?:Road|Rd|Street|St|Avenue|Ave|Drive|Dr|Valley|Lane|Crescent|Close|Way|Park|Quay|Terrace|Walk|Place|Link|Grove|Hill|View|Rise|Boulevard|Blvd)", q)
        if m2: candidates.append(m2.group(0))
        for c in candidates:
            out = onemap(c)
            time.sleep(0.3)
            if out: break
    GEO_CACHE[q] = out
    return out

import subprocess
def route(p, d):
    # macOS system python's LibreSSL can't handshake with OSRM — use curl
    url = (f"https://router.project-osrm.org/route/v1/driving/"
           f"{p[1]},{p[0]};{d[1]},{d[0]}?overview=false")
    try:
        raw = subprocess.run(["curl", "-s", "-m", "15", url], capture_output=True, text=True).stdout
        r = json.loads(raw)["routes"][0]
        time.sleep(0.6)
        return r["distance"] / 1000, (r["duration"] / 60) * 1.35  # same padding as app
    except Exception:
        time.sleep(0.6)
        return None

def dist_km(a, b):
    dlat, dlon = math.radians(b[0]-a[0]), math.radians(b[1]-a[1])
    s = math.sin(dlat/2)**2 + math.cos(math.radians(a[0]))*math.cos(math.radians(b[0]))*math.sin(dlon/2)**2
    return 2*6371*math.asin(math.sqrt(s))

def context(dt, pickup_ll):
    dow, t = dt.weekday(), dt.hour + dt.minute/60  # weekday(): Mon=0
    weekday = dow <= 4
    return dict(
        phvPeak=(weekday and 7 <= t < 9.5) or (17 <= t < 20),
        lateNight=t < 6,
        airport=pickup_ll is not None and dist_km(pickup_ll, CHANGI) < 2.5,
        airportEvening=t >= 17 and dow in (4, 5, 6),
    )

def model_phv(svc, km, mins, ctx):
    s = SERVICES[svc]
    mid = s["base"] + s["perKm"]*km + s["perMin"]*mins + s["fee"]
    if ctx["airport"]: mid += 5 if ctx["airportEvening"] else 3
    if ctx["lateNight"]: mid *= 1.20
    elif ctx["phvPeak"]: mid *= 1.18
    return mid

def bucket(ctx):
    return "late" if ctx["lateNight"] else ("peak" if ctx["phvPeak"] else "off")

rides = json.load(open(f"{SCRATCH}/rides.json"))
rows, skipped = [], []
for r in rides:
    svc = r["service"]
    if svc not in SERVICES and svc != "zig":
        continue
    dt = datetime.fromisoformat(r["dt"])
    p = geocode(r["from"]) if r.get("from") else None
    d = geocode(r["to"]) if r.get("to") else None
    km = mins = None
    if p and d:
        rt = route(p, d)
        if rt: km, mins = rt
    # fall back to receipt-stated values where routing failed
    if km is None and r.get("dist_km"): km = r["dist_km"]
    if mins is None and r.get("dur_min"): mins = r["dur_min"]
    if km is None or mins is None:
        skipped.append((svc, r["dt"], "no route/distance"))
        continue
    actual = r["total"] - (r.get("toll") or 0)
    if r.get("multistop"): actual -= 5  # strip multi-destination fee
    ctx = context(dt, p)
    if svc == "zig":
        rows.append(dict(svc=svc, dt=r["dt"], km=km, mins=mins, actual=actual,
                         modelled=None, ratio=None, bucket=bucket(ctx)))
        continue
    modelled = model_phv(svc, km, mins, ctx)
    rows.append(dict(svc=svc, dt=r["dt"], km=round(km,1), mins=round(mins,1),
                     actual=actual, modelled=round(modelled,2),
                     ratio=round(actual/modelled, 3), bucket=bucket(ctx)))

print(f"{len(rows)} rides usable, {len(skipped)} skipped: {skipped}")
out = {}
for svc in SERVICES:
    rs = [x["ratio"] for x in rows if x["svc"] == svc]
    if len(rs) < 3:
        print(f"{svc}: only {len(rs)} rides — leaving uncalibrated")
        continue
    f = median(rs)
    # spread: 1.5 × median absolute relative deviation — robust to surge outliers
    dev = sorted(abs(x/f - 1) for x in rs)
    spread = min(max(1.5 * median(dev), 0.08), 0.18)
    out[svc] = dict(factor=round(f, 3), spread=round(spread, 3), n=len(rs))
    per_bucket = {b: [x["ratio"] for x in rows if x["svc"] == svc and x["bucket"] == b] for b in ("off","peak","late")}
    print(f"{svc}: factor={f:.3f} spread={spread:.3f} n={len(rs)} | bucket medians:",
          {b: (round(median(v),3), len(v)) for b, v in per_bucket.items() if v})
zig = [x for x in rows if x["svc"] == "zig"]
if zig:
    print("zig fixed-fare receipts (info only):", [(x["dt"], x["actual"], x["km"]) for x in zig])
json.dump(out, open(f"{SCRATCH}/calibration.json", "w"), indent=2)
json.dump(rows, open(f"{SCRATCH}/rows_debug.json", "w"), indent=2)
print("\nCALIBRATION:", json.dumps(out))
