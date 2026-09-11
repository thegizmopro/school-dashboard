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
# listing detection mirrors gen_digest.py: strong sale verbs everywhere; bare
# "$N"/"free" only in the free-trade group ("free" outside it must not be an event)
SALE_STRONG = re.compile(r"for sale|iso\b|selling|give ?away|giveaway|wtb", re.I)
SALE_EVENTISH = re.compile(r"\b(event|potluck|activity|class|workshop|program|gathering|webinar|community|parade|festival|performance|movie)\b", re.I)
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
            is_sale = bool(group == "harmony-sc" or SALE_STRONG.search(text)
                           or (re.search(r"\bfree\b", text, re.I) and not SALE_EVENTISH.search(text)))
            if is_sale:
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
           "campaign": "Parent-run since 1989, shARK's ~$75K a year all stays right here: $50K in school grants, the rest as classroom wishes, community events, and appreciation for our teachers. Thank you, shARK families! 💚",
           "events": events}
    write_json(DATA / "shark.json", out)
    return f"shark: {len(events)} events (dated: {sum(1 for e in events if e.get('date'))})"

# ---------------- Merged calendar feed ----------------
# one subscribable .ics: school-year dates + shARK events + ParentSquare feed
# + dated notices. Regenerated every run; UIDs are stable so subscribers see
# updates instead of duplicates.
def _ics_escape(s):
    return (s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
             .replace("\r", "").replace("\n", "\\n"))

def _fold(line):
    # RFC5545: lines wrap at 75 octets, continuations start with a space
    b = line.encode("utf-8")
    parts = []
    while len(b) > 73:
        cut = 73
        while cut > 0 and (b[cut] & 0xC0) == 0x80:
            cut -= 1
        parts.append(b[:cut].decode("utf-8"))
        b = b[cut:]
    parts.append(b.decode("utf-8"))
    return "\r\n ".join(parts)

def _canon(t):
    """Canonical event-family token so the same event under different names
    across sources dedupes ("Harvest Gather TBD" == "Autumn Gather")."""
    s = t.lower()
    if "break" in s and "winter" in s: return "winter break"
    if "break" in s and "thanksgiving" in s: return "thanksgiving break"
    if "break" in s and "spring" in s: return "spring break"
    if "board meeting" in s: return "board meeting"
    if re.search(r"no school|staff development|in-?service", s): return "no-school-day"
    if "gather" in s: return "gather"
    if "festiv" in s and re.search(r"autumn|fall|harvest", s): return "fall festival"
    if "festiv" in s and "spring" in s: return "spring festival"
    if re.search(r"move\s*-?\s*a\s*-?\s*thon", s): return "move-a-thon"
    if "pancake" in s: return "pancake breakfast"
    if "tree lighting" in s: return "tree lighting"
    if "winter" in s and re.search(r"lantern|concert|festival|walk", s): return "winter festival"
    return s

def write_calendar_ics():
    now = datetime.datetime.now().strftime("%Y%m%dT%H%M%SZ")
    evs = {}
    seen = set()          # (date, canon) — first source wins: yc -> shARK -> notices -> PS -> district
    ns_dates = set()      # every date the structural calendar says has no school

    def add(uid, date, summary, time=None, url=None):
        key = (date, _canon(summary))
        if key in seen:
            return
        seen.add(key)
        evs[uid] = (date, summary, time, url)

    try:
        yc = json.loads((DATA / "calendar-year.json").read_text(encoding="utf-8"))
        for d in yc.get("keyDates", []):
            if not d.get("date"):
                continue
            add(f"husd-{d['date']}-{d.get('kind','x')}", d["date"], d["label"])
            if d.get("kind") in ("holiday", "no_school"):
                ns_dates.add(d["date"])
            if d.get("kind") == "break" and isinstance(d.get("range"), list):
                start = datetime.date.fromisoformat(d["range"][0])
                end = datetime.date.fromisoformat(d["range"][1])
                while start <= end:
                    ns_dates.add(start.isoformat())
                    start += datetime.timedelta(days=1)
    except Exception:
        pass

    try:
        sk = json.loads((DATA / "shark.json").read_text(encoding="utf-8"))
        for e in sk.get("events", []):
            if e.get("date") and e.get("title"):
                slug = re.sub(r"[^a-z0-9]+", "-", e["title"].lower())[:30]
                add(f"shark-{e['date']}-{slug}", e["date"], e["title"])
    except Exception:
        pass

    # notices that name a date (e.g. "workshop — Sep 11") become all-day events
    months = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
    try:
        nz = json.loads((DATA / "notices.json").read_text(encoding="utf-8"))
        for n in nz.get("notices", []):
            blob = f"{n.get('title','')} {n.get('text','')}"
            m = re.search(rf"\b({months})[a-z]*\.?\s+(\d{{1,2}})\b", blob)
            if not m:
                continue
            try:
                y = datetime.date.today().year
                dt = datetime.datetime.strptime(f"{m.group(1)} {m.group(2)} {y}", "%b %d %Y").date()
                if dt < datetime.date.today():
                    dt = dt.replace(year=y + 1)   # "May 5" mentioned in Sept -> next May
            except ValueError:
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", (n.get("title") or "notice").lower())[:40]
            add(f"notice-{slug}", dt.isoformat(), n.get("title", "Notice"))
    except Exception:
        pass

    # ParentSquare feed (timed events keep their clock time, floating local);
    # board meetings carry the live meeting link so calendar subscribers get it too
    board_url = None
    try:
        bd = json.loads((DATA / "board.json").read_text(encoding="utf-8"))
        board_url = bd.get("meeting_url") or bd.get("listing_url")
    except Exception:
        pass
    try:
        flat = re.sub(r"\r?\n[ \t]", "", (DATA / "parentsquare-live.ics").read_text(encoding="utf-8", errors="replace"))
        for b in flat.split("BEGIN:VEVENT")[1:]:
            dt = re.search(r"DTSTART[^:\n]*:(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2}))?", b)
            sm = re.search(r"SUMMARY:([^\r\n]+)", b)
            if not dt or not sm:
                continue
            title = re.sub(r"^Copy of ", "", sm.group(1).strip())
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower())[:40]
            url = board_url if re.search(r"board meeting", title, re.I) else None
            add(f"ps-{dt[1]}-{dt[2]}-{dt[3]}-{slug}", f"{dt[1]}-{dt[2]}-{dt[3]}", title,
                time=f"{dt[4]}{dt[5]}" if dt[4] else None, url=url)
    except Exception:
        pass

    # district master calendar — full-year events; structural-calendar duplicates
    # (per-day no-school/break entries) are suppressed since yc already covers them
    try:
        flatd = re.sub(r"\r?\n[ \t]", "", (DATA / "district-calendar.ics").read_text(encoding="utf-8", errors="replace"))
        for b in flatd.split("BEGIN:VEVENT")[1:]:
            dt = re.search(r"DTSTART[^:\n]*:(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2}))?", b)
            sm = re.search(r"SUMMARY:([^\r\n]*)", b)
            if not dt or not sm:
                continue
            date = f"{dt[1]}-{dt[2]}-{dt[3]}"
            title = sm.group(1).strip()
            if _canon(title) in ("no-school-day", "winter break", "thanksgiving break", "spring break") and date in ns_dates:
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower())[:40]
            url = board_url if re.search(r"board meeting", title, re.I) else None
            add(f"district-{date}-{slug}", date, title,
                time=f"{dt[4]}{dt[5]}" if dt[4] else None, url=url)
    except Exception:
        pass

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
             "PRODID:-//Harmony Today//Family Dashboard//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             "X-WR-CALNAME:Harmony Today",
             f"DTSTAMP:{now}"]
    for uid, (date, summary, time, url) in sorted(evs.items(), key=lambda kv: (kv[1][0], kv[1][2] or "")):
        lines += ["BEGIN:VEVENT",
                  f"UID:{uid}@harmony-today",
                  f"DTSTAMP:{now}",
                  f"DTSTART;VALUE=DATE:{date.replace('-', '')}" if not time
                  else f"DTSTART:{date.replace('-', '')}T{time}00",
                  f"SUMMARY:{_ics_escape(summary)}"]
        if url:
            lines.append(f"URL:{_ics_escape(url)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    with open(DATA / "all-events.ics", "w", encoding="utf-8", newline="") as f:   # newline="": no CRLF translation on Windows
        f.write("\r\n".join(_fold(l) for l in lines) + "\r\n")
    return f"calendar ics: {len(evs)} events"

# ---------------- Board meetings ----------------
# the district homepage carries a standing "Board Meeting Link" (updated per
# meeting) — scrape it so dashboard rows deep-link into the live meeting,
# with the Simbli meeting listing as fallback/agenda archive.
SIMBLI_LISTING = "https://simbli.eboardsolutions.com/SB_Meetings/SB_MeetingListing.aspx?S=36030644"

def fetch_board():
    meeting_url = None
    try:
        raw = fetch("https://www.harmonyusd.org/", timeout=20).decode("utf-8", errors="replace")
        m = re.search(r'Board Meeting Link:.*?<a[^>]+href="(https?://[^"]+)"', raw, re.I | re.S)
        if m:
            meeting_url = m.group(1)
    except Exception:
        pass
    write_json(DATA / "board.json", {"fetched": datetime.datetime.now().isoformat(timespec="seconds"),
                                     "meeting_url": meeting_url, "listing_url": SIMBLI_LISTING})
    return f"board: {'meeting link ok' if meeting_url else 'listing only (homepage link not found)'}"

# ---------------- District master calendar ----------------
# the district's own full-year feed (80+ events): the authoritative EVENTS layer.
# calendar-year.json stays the structural layer (breaks/kinds/ranges); shARK keeps
# its curated linked events; ParentSquare adds near-term items this feed misses.
DISTRICT_CAL = "https://harmonyusd.org/sndreq/generateCalendarICS.php?calendar_id=136424"

def fetch_district_cal():
    data = fetch(DISTRICT_CAL).decode("utf-8", errors="replace")
    (DATA / "district-calendar.ics").write_text(data, encoding="utf-8")
    n = data.count("BEGIN:VEVENT")
    return f"district cal: {n} events"

# ---------------- Runner ----------------
def main():
    results = []
    results.append(scan_whatsapp())
    results.append(fetch_ical())
    results.append(fetch_district_cal())
    results.append(fetch_board())
    results.append(write_calendar_ics())
    results.append(fetch_weather())
    if stale("menu-linq.json", 20):
        results.append(fetch_linq())
    if stale("shark.json", 24 * 6):
        results.append(fetch_shark())
    print(" | ".join(results))

if __name__ == "__main__":
    main()
