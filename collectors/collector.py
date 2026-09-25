"""
Harmony Today — data collector (cron 4x daily: 00/06/12/18 PT)

Every run: WhatsApp scan (local-only output) · ParentSquare iCal · district
master calendar (harmonyusd.org — the authoritative events layer) · board-meeting
link (scraped off the district homepage) · merged all-events.ics · weather.
Staleness-gated: LINQ menu (>20h) · shARK events (>6 days) — a missed cron
self-heals on the next run.

Each step is fault-isolated: a failed fetch logs and skips; the last good file
stays on disk; the remaining sources still refresh and the cron still commits.

Secrets/paths live in collectors/local-config.json (gitignored — see
local-config.example.json): parentsquare_ics URL + WhatsApp log paths.

Output split (privacy):
  site/data/    — published to the web (weather, both ics feeds, board.json,
                  shark.json, menu-linq.json, all-events.ics, community-digest.json)
  data/         — LOCAL pipeline state only (raw WhatsApp feed — real names and
                  chat text must NEVER be deployed), scan-state
Writes JSON files, then leaves git commit/push to the caller.
"""
import json, re, io, os, sys, urllib.request, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent   # survives a moved checkout
DATA = ROOT / "site" / "data"      # published
LOCAL = ROOT / "data"              # local-only pipeline state
DATA.mkdir(parents=True, exist_ok=True)
LOCAL.mkdir(parents=True, exist_ok=True)

# local, gitignored: {"parentsquare_ics": "...", "whatsapp_logs": [...]}
try:
    CONFIG = json.loads((ROOT / "collectors" / "local-config.json").read_text(encoding="utf-8"))
except Exception:
    CONFIG = {}

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
KEYWORDS = re.compile(r"no school|reminder|due|early release|half day|forms?|field trip|meeting|event|fundrais|volunteer|picture day|book fair|conference|spirit|schedule|cancelled|canceled|sold|free|for sale|iso|looking for|heads up|alert|tickets?|last weekend|demonstration|open to|invited|season", re.I)
LOGS = [pathlib.Path(p) for p in CONFIG.get("whatsapp_logs", [])]
STATE = ROOT / "collectors" / "scan-state.json"

# NOTE: listing detection lives ONLY in gen_digest.py (it re-reads the logs) —
# keeping one copy of those rules prevents drift.
def scan_whatsapp():
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    items = []
    for log in LOGS:
        if not log.exists(): continue
        group = "salmon-creek" if "salmon" in log.name else "harmony-sc"
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        pos = state.get(log.name, 0)
        for i, line in enumerate(lines[pos:], start=pos):
            m = re.match(r"\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})\] \[([^\]]+)\] ([^:]+): (.*)", line)
            if not m: continue
            date, time, g, sender, text = m.groups()
            if KEYWORDS.search(text):
                items.append({"date": date, "time": time, "group": g, "who": sender.strip(),
                              "text": text.strip()[:300], "url": first_url(text)})
        state[log.name] = len(lines)
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state))
    feed = {"scanned": datetime.datetime.now().isoformat(timespec="seconds"),
            "items": items[-25:]}
    write_json(LOCAL / "community-feed.json", feed)   # local ONLY — real names/chat text
    return f"whatsapp: {len(items)} notable"

# ---------------- iCal fetch ----------------
ICAL_URL = CONFIG.get("parentsquare_ics")   # private feed token — local-config.json, gitignored

def _notice_vevents():
    """VEVENT blocks for notices that name a date (and optionally a time, e.g.
    board-meeting posts). The dashboard calendar card renders parentsquare-live.ics,
    but ParentSquare posts aren't events in their feed - so we merge them in here."""
    months = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
    now = datetime.datetime.now().strftime("%Y%m%dT%H%M%SZ")
    out, today = [], datetime.date.today()
    try:
        nz = json.loads((DATA / "notices.json").read_text(encoding="utf-8"))
    except Exception:
        return out
    for n_ in nz.get("notices", []):
        blob = f"{n_.get('title','')} {n_.get('text','')}"
        m = re.search(rf"\b({months})[a-z]*\.?\s+(\d{{1,2}})\b", blob)
        if not m:
            continue
        try:
            dt = datetime.datetime.strptime(f"{m.group(1)} {m.group(2)} {today.year}", "%b %d %Y").date()
            if dt < today:
                dt = dt.replace(year=today.year + 1)
        except ValueError:
            continue
        tm = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", blob, re.I)
        start = f"{dt.strftime('%Y%m%d')}"
        if tm:
            hh = int(tm.group(1)) % 12 + (12 if tm.group(3).lower() == "pm" else 0)
            start += f"T{hh:02d}{int(tm.group(2) or 0):02d}00"
        slug = re.sub(r"[^a-z0-9]+", "-", (n_.get("title") or "notice").lower())[:40]
        url = n_.get("url")
        out.append("\r\n".join([
            "BEGIN:VEVENT",
            f"UID:notice-{slug}@harmony-today",
            f"DTSTAMP:{now}",
            f"DTSTART{';VALUE=DATE' if len(start) == 8 else ''}:{start}",
            f"SUMMARY:{_ics_escape(n_.get('title', 'Notice'))}",
        ] + ([f"URL:{_ics_escape(url)}"] if url else []) + ["END:VEVENT"]))
    return out

def fetch_ical():
    if not ICAL_URL:
        raise RuntimeError("parentsquare_ics missing from collectors/local-config.json (see local-config.example.json)")
    data = fetch(ICAL_URL).decode("utf-8", errors="replace")
    extra = _notice_vevents()
    if extra:
        data = data.replace("END:VCALENDAR", "\r\n".join(extra) + "\r\nEND:VCALENDAR")
    (DATA / "parentsquare-live.ics").write_text(data, encoding="utf-8")
    n = data.count("BEGIN:VEVENT")
    return f"ical: {n} events (incl. {len(extra)} notice-derived)"

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
    # primary: the page's own embedded JS data — { date: "2026-10-03", title: ... }
    # (pre-Sep-2026 format; kept in case it returns)
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

    # secondary: the rendered event list (Next.js site rebuild, Sep 2026) —
    # <li class="ev"> with ev__date "Sep 18", h2/h3 title (often a link to the
    # event page), and an ev__where "6–9pm · Location" line
    if not events:
        MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        today = datetime.date.today()
        for b in re.finditer(r'<li class="ev[^"]*">(.*?)</li>', raw, re.S):
            blob = b.group(1)
            dm = re.search(r'ev__date">([A-Z][a-z]{2})\s+(\d{1,2})<', blob)
            tm = re.search(r'<h[23][^>]*>(?:<a[^>]*>)?([^<]+)', blob)
            if not dm or not tm:
                continue
            try:
                mon = MONTHS.index(dm.group(1)) + 1
                d = datetime.date(today.year, mon, int(dm.group(2)))
                if d < today - datetime.timedelta(days=45):
                    d = datetime.date(today.year + 1, mon, int(dm.group(2)))
            except ValueError:
                continue
            wt, wl = None, None
            where = re.search(r'ev__where">(.*?)(?:</p>|$)', blob, re.S)
            if where:
                parts = [p.strip() for p in re.sub(r"<!--.*?-->", "", where.group(1)).split("·")]
                if parts and parts[0]:
                    wt = _unesc(parts[0])
                if len(parts) > 1 and parts[1]:
                    wl = _unesc(parts[1])
            am = re.search(r'<a href="(/[^"]+)"', blob)
            url = SHARK_URL.rstrip("/") + am.group(1) if am else None
            events.append({"date": d.isoformat(), "title": _unesc(tm.group(1)).strip(),
                           "time": wt, "location": wl, "url": url})

    # tertiary: bare h3 titles (no dates) if the page is restructured again
    if not events:
        seen_titles = set()
        for m in re.finditer(r"<h3[^>]*>(?:<a[^>]*>)?([^<]+)</h3>", raw):
            t = _unesc(m.group(1)).strip()
            if t and t not in seen_titles and "ROLE" not in t.upper():
                seen_titles.add(t)
                events.append({"title": t})
    out = {"fetched": datetime.datetime.now().isoformat(timespec="seconds"),
           "url": SHARK_URL,
           "campaign": "Parent-run since 1989, shARK's ~$75K a year all stays right here: $50K in school grants, the rest as classroom wishes, community events, and appreciation for our teachers. Thank you, shARK families! 💚",
           "events": events}
    # empty-scrape = failure, not "season over": keep the last good events
    if not any(e.get("date") for e in events):
        try:
            prev = json.loads((DATA / "shark.json").read_text(encoding="utf-8"))
            if any(e.get("date") for e in prev.get("events", [])):
                out["events"] = prev["events"]
                out["fetched"] = prev.get("fetched", out["fetched"])
                out["warning"] = "scrape found no dated events — kept previous data"
        except Exception:
            pass
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
            # carry a time when the notice names one ("8:45pm") so board meetings
            # show as timed rows in the calendar, not all-day blocks
            tm = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", blob, re.I)
            tstr = None
            if tm:
                hh = int(tm.group(1)) % 12 + (12 if tm.group(3).lower() == "pm" else 0)
                tstr = f"{hh:02d}{int(tm.group(2) or 0):02d}"
            add(f"notice-{slug}", dt.isoformat(), n.get("title", "Notice"), time=tstr, url=n.get("url"))
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

# ---------------- Absence emails ----------------
# harmonyusd.org/report-an-absence maps each grade to its own absence email
# (kinderabsence@, firstgradeabsence@, ... tkabsence@). Scrape every run;
# keep the last good file if the page stops yielding emails.
ABSENCE_URL = "https://www.harmonyusd.org/report-an-absence"
ABSENCE_LABELS = [("tk", "TK"), ("kinder", "Kindergarten"), ("firstgrade", "1st Grade"),
                  ("secondgrade", "2nd Grade"), ("3rdgrade", "3rd Grade"),
                  ("4thgrade", "4th Grade"), ("5thgrade", "5th Grade"),
                  ("6thgrade", "6th Grade"), ("7thgrade", "7th Grade"),
                  ("8thgrade", "8th Grade")]

def fetch_absence():
    raw = fetch(ABSENCE_URL, timeout=20).decode("utf-8", errors="replace")
    found = sorted(set(re.findall(r"([a-z0-9]+)absence@harmonyusd\.org", raw)))
    if not found:
        prev = DATA / "absence.json"
        if prev.exists():
            return "absence: no emails found on page — kept previous"
        raise RuntimeError("no absence emails found on district page")
    order = {p: i for i, (p, _) in enumerate(ABSENCE_LABELS)}
    found.sort(key=lambda p: order.get(p, 99))
    grades = [{"grade": dict(ABSENCE_LABELS).get(p, p.capitalize()), "email": f"{p}absence@harmonyusd.org"}
              for p in found]
    write_json(DATA / "absence.json", {"fetched": datetime.datetime.now().isoformat(timespec="seconds"),
                                       "source": ABSENCE_URL, "grades": grades})
    return f"absence: {len(grades)} grades"

# ---------------- Runner ----------------
def main():
    steps = [scan_whatsapp, fetch_ical, fetch_district_cal, fetch_board,
             fetch_absence, write_calendar_ics, fetch_weather]
    if stale("menu-linq.json", 20):
        steps.append(fetch_linq)
    if stale("shark.json", 24 * 6):
        steps.append(fetch_shark)
    results, failures = [], []
    for step in steps:
        try:
            results.append(str(step()))
        except Exception as e:
            # fault-isolated: last good file stays, other sources still refresh,
            # and the run still exits 0 so the cron commits what succeeded
            failures.append(f"{step.__name__}: FAILED ({e})")
    if failures:
        print("WARNINGS: " + " | ".join(failures))
    print(" | ".join(results))

if __name__ == "__main__":
    main()
