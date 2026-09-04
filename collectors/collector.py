"""
Harmony Today — data collector (tiered, 4x daily)
Runs: WhatsApp scan + iCal fetch ALWAYS; weather + LINQ daily (6am); shARK weekly (Mon)
Writes JSON files into site/data/, then leaves git commit/push to caller.
"""
import json, re, io, os, sys, urllib.request, datetime, pathlib

ROOT = pathlib.Path(r"C:\dev\school-dashboard")
DATA = ROOT / "site" / "data"
DATA.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HarmonyToday/1.0",
      "Origin": "https://linqconnect.com", "Referer": "https://linqconnect.com/"}

def fetch(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def write_json(name, obj):
    p = DATA / name
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {name} ({p.stat().st_size} bytes)")

def now_pst():
    return datetime.datetime.now()

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
                                 "price": (re.search(r"\$\d+[\d,\.]*", text) or [None])[0] if re.search(r"\$", text) else "Free?" if re.search(r"\bfree\b", text, re.I) else "—"})
            if KEYWORDS.search(text):
                items.append({"date": date, "time": time, "group": g, "who": sender.strip(),
                              "text": text.strip()[:300]})
        state[log.name] = len(lines)
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state))
    feed = {"scanned": now_pst().isoformat(timespec="seconds"),
            "items": items[-25:],
            "listings": listings[-20:]}
    write_json("community-feed.json", feed)
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
    out = {"updated": now_pst().isoformat(timespec="seconds"),
           "temp": raw["current"]["temperature_2m"],
           "code": raw["current"]["weather_code"],
           "daily": [{"date": d, "hi": raw["daily"]["temperature_2m_max"][i],
                      "lo": raw["daily"]["temperature_2m_min"][i],
                      "code": raw["daily"]["weather_code"][i]}
                     for i, d in enumerate(raw["daily"]["time"])]}
    write_json("weather.json", out)
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
    write_json("menu-linq.json", {"fetched": now_pst().isoformat(timespec="seconds"), "days": out_days})
    return f"linq: {len(out_days)} days"

# ---------------- shARK ----------------
def fetch_shark():
    raw = fetch("https://www.harmonyark.org/").decode("utf-8", errors="replace")
    # light extraction: the site is hand-built; grab the events block markers
    events = []
    for m in re.finditer(r"<h3[^>]*>\s*<a[^>]*>([^<]+)</a>|<h3[^>]*>([^<]+)</h3>", raw):
        title = (m.group(1) or m.group(2) or "").strip()
        if title and title not in [e["title"] for e in events]:
            events.append({"title": title})
    out = {"fetched": now_pst().isoformat(timespec="seconds"),
           "url": "https://www.harmonyark.org/",
           "campaign": "shARK raises ~$75K/yr: $50K block grants to the school, rest to events, classroom requests, staff appreciation",
           "events": events[:10]}
    write_json("shark.json", out)
    return f"shark: {len(events)} event titles"

# ---------------- Runner ----------------
def main():
    hour = now_pst().hour
    weekday = now_pst().weekday()  # 0=Mon
    results = []
    results.append(scan_whatsapp())
    results.append(fetch_ical())
    if hour < 9:  # 6am run does daily refreshes
        results.append(fetch_weather())
        results.append(fetch_linq())
        if weekday == 0:
            results.append(fetch_shark())
    print(" | ".join(results))

if __name__ == "__main__":
    main()
