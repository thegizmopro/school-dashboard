"""
Harmony Today — data collector (tiered, 4x daily)
Runs: WhatsApp scan + iCal fetch + weather ALWAYS; LINQ/shARK refresh only when
their JSON is stale (LINQ > 20h, shARK > 6 days) so a missed 6am cron never
leaves data frozen for a whole day.

Output split (privacy):
  site/data/    — published to the web: ics, weather, menu-linq, shark, community-digest
  data/         — LOCAL pipeline state only: raw-ish WhatsApp feed (names + chat text
                  must never be deployed), scan-state
Writes JSON files, then leaves git commit/push to caller.
"""
import json, re, io, os, sys, urllib.request, datetime, pathlib

ROOT = pathlib.Path(r"C:\dev\school-dashboard")
DATA = ROOT / "site" / "data"      # published
LOCAL = ROOT / "data"              # local-only pipeline state
DATA.mkdir(parents=True, exist_ok=True)
LOCAL.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HarmonyToday/1.0",
      "Origin": "https://linqconnect.com",
      "Referer": "https://linqconnect.com/"}

def fetch(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def write_json(path, obj):
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {p.relative_to(ROOT)} ({p.stat().st_size} bytes)")

def stale(name, hours):
    """True when site/data/<name> is missing, unreadable, or its 'fetched' stamp is older than hours."""
    p = DATA / name
    if not p.exists(): return True
    try:
        fetched = json.loads(p.read_text(encoding="utf-8")).get("fetched", "")
        age = datetime.datetime.now() - datetime.datetime.fromisoformat(fetched)
        return age.total_seconds() > hours * 3600
    except Exception:
        return True

def first_url(text):
    m = re.search(r"https?://\S+", text or "")
    return m.group(0).rstrip(".,)!") if m else None

# ---------------- WhatsApp scan ----------------
KEYWORDS = re.compile(r"no school|reminder|due|early release|half day|forms?|field trip|meeting|event|fundrais|volunteer|picture day|book fair|conference|spirit|schedule|cancelled|canceled|sold|free|for sale|iso|looking for|heads up|alert", re.I)
LOGS = [
    pathlib.Path(r"C:\Users\kenzo\SynologyDrive\projects\whatsapp\whatsapp-salmon-creek.md"),
    pathlib.Path(r"C:\Users\kenzo\SynologyDrive\projects\whatsapp\whatsapp-harmony-sc-free-trade-sell.md"),
]
STATE = ROOT / "collectors" / "scan-state.json"

def scan_whatsapp():
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    items, listings = [], []
    for log in LOGS:
        if not log.exists(): continue
        group = "salmon-creek" if "salmon" in log.name else "harmony-sc"
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        pos = state.get(log.name, 0)
        for i, line in enumerate(lines[pos:], start=pos):
            m = re.match(r"\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})\] \[([^\]]+)\] ([^:]+): (.*)", line)
            if not m: continue
            date, time, g, sender, text = m.groups()
            if re.search(r"for sale|\$\d|free\b|iso\b|selling|give away|giveaway", text, re.I) or group == "harmony-sc":
                listings.append({"date": date, "group": g, "who": sender.strip(),
                                 "text": text.strip()[:200],
                                 "url": first_url(text),
                                 "price": (re.search(r"\$\d+[\d,\.]*", text) or [None])[0] if re.search(r"\$", text) else "Free?" if re.search(r"\bfree\b", text, re.I) else "—"})
            if KEYWORDS.search(text):
                items.append({"date": date, "time": time, "group": g, "who": sender.strip(),
                              "text": text.strip()[:300], "url": first_url(text)})
        state[log.name] = len(lines)
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state))
    feed = {"scanned": datetime.datetime.now().isoformat(timespec="seconds"),
            "items": items[-25:],
            "listings": listings[-20:]}
    write_json(LOCAL / "community-feed.json", feed)   # local ONLY — real names/chat text
    return f"whatsapp: {len(items)} notable, {len(listings)} listings"

# ---------------- iCal fetch ----------------
ICAL_URL = "https://www.parentsquare.com/schools/18160/users/MhJf0v_6IaRclQY_Yj1Itg/calendar.ics"

def fetch_ical():
    data = fetch(ICAL_URL).decode("utf-8", errors="replace")
    (DATA / "parentsquare-live.ics").write_text(data, encoding="utf-8")
    n = data.count("BEGIN:VEVENT")
    return f"ical: {n} events"

# ---------------- Weather ----------------
# Occidental, CA
LAT, LON = 38.4053, -122.9424

def fetch_weather():
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
           f"&current=temperature_2m,weather_code&daily=temperature_2m_max,temperature_2m_min,weather_code"
           f"&temperature_unit=fahrenheit&timezone=America%2FLos_Angeles&forecast_days=5")
    raw = json.loads(fetch(url).decode())
    out = {"updated": datetime.datetime.now().isoformat(timespec="seconds"),
           "temp": raw["current"]["temperature_2m"],
           "code": raw["current"]["weather_code"],
           "daily": [{"date": d, "hi": raw["daily"]["temperature_2m_max"][i],
                      "lo": raw["daily"]["temperature_2m_min"][i],
                      "code": raw["daily"]["weather_code"][i]}
                     for i, d in enumerate(raw["daily"]["time"])]}
    write_json(DATA / "weather.json", out)
    return "weather: ok"

# ---------------- LINQ menu ----------------
LINQ = ("https://api.linqconnect.com/api/FamilyMenu?buildingId=c6b2e3f4-82bd-ef11-8321-e7236f8c8a07"
        "&districtId=34ae3846-e8b0-ef11-8321-94f035f3f81f&startDate={start}&endDate={end}")

def fetch_linq():
    today = datetime.date.today()
    def mdY(d):
        return f"{d.month}-{d.day}-{d.year}"
    url = LINQ.format(start=mdY(today - datetime.timedelta(days=2)),
                      end=mdY(today + datetime.timedelta(days=45)))
    raw = json.loads(fetch(url).decode())
    out_days = {}
    for sess in raw.get("FamilyMenuSessions", []):
        session = sess.get("ServingSession")
        for plan in sess.get("MenuPlans", []):
            for day in plan.get("Days", []):
                try:
                    dt = datetime.datetime.strptime(day["Date"], "%m/%d/%Y").date()
                except Exception:
                    continue
                iso = dt.isoformat()
                entry = out_days.setdefault(iso, {"lunch": None, "breakfast": None})
                meals = []
                for meal in day.get("MenuMeals", []):
                    for cat in meal.get("RecipeCategories", []):
                        for r in cat.get("Recipes", []):
                            meals.append({"cat": cat.get("CategoryName"), "item": r.get("RecipeName")})
                if session == "Lunch" and meals:
                    entry["lunch"] = meals
                elif session == "Breakfast" and meals:
                    entry["breakfast"] = meals
    write_json(DATA / "menu-linq.json", {"fetched": datetime.datetime.now().isoformat(timespec="seconds"), "days": out_days})
    return f"linq: {len(out_days)} days"

# ---------------- shARK ----------------
SHARK_URL = "https://www.harmonyark.org/"

def _unesc(s):
    """harmonyark.org embeds its event data as JS object literals with \\uXXXX escapes."""
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)

def fetch_shark():
    raw = fetch(SHARK_URL).decode("utf-8", errors="replace")
    events = []
    # primary: the page's own embedded data — { date: "2026-10-03", title: "Autumn Gather", time, location, tickets, page }
    for m in re.finditer(r'\{\s*date:\s*"(\d{4}-\d{2}-\d{2})"\s*,\s*title:\s*"([^"]+)"[^}]*\}', raw):
        date, title = m.group(1), _unesc(m.group(2)).strip()
        blob = m.group(0)
        tickets = re.search(r'tickets:\s*"(https?://[^"]+)"', blob)
        page = re.search(r'page:\s*"(/[^"]*)"', blob)
        url = tickets.group(1) if tickets else (SHARK_URL.rstrip("/") + page.group(1) if page else None)
        tm = re.search(r'time:\s*"([^"]+)"', blob)
        loc = re.search(r'location:\s*"([^"]+)"', blob)
        events.append({"date": date, "title": title,
                       "time": _unesc(tm.group(1)) if tm else None,
                       "location": _unesc(loc.group(1)) if loc else None,
                       "url": url})
    # fallback: bare h3 titles (no dates) if the embedded data ever moves
    if not events:
        seen = set()
        for m in re.finditer(r"<h3[^>]*>([^<]+)</h3>", raw):
            t = m.group(1).strip()
            if t and t not in seen and "ROLE" not in t.upper():
                seen.add(t)
                events.append({"title": t})
    out = {"fetched": datetime.datetime.now().isoformat(timespec="seconds"),
           "url": SHARK_URL,
           "campaign": "shARK raises ~$75K/yr: $50K block grants to the school, rest to events, classroom requests, staff appreciation",
           "events": events}
    write_json(DATA / "shark.json", out)
    return f"shark: {len(events)} events (dated: {sum(1 for e in events if e.get('date'))})"

# ---------------- Runner ----------------
def main():
    results = []
    results.append(scan_whatsapp())
    results.append(fetch_ical())
    results.append(fetch_weather())
    if stale("menu-linq.json", 20):
        results.append(fetch_linq())
    if stale("shark.json", 24 * 6):
        results.append(fetch_shark())
    print(" | ".join(results))

if __name__ == "__main__":
    main()
