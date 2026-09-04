# School Dashboard — Project Spec (v0.1 draft)

_Purpose: a single attractive, auto-updating dashboard for the kids' school — upcoming dates, countdowns, lunch menu by day, weather. Fun for kids, informative for parents._
_Status: SPEC PHASE — no code yet. 2026-09-03._

---

## 1. Goals

1. **One place** for school info instead of 4-5 scattered sources
2. **At-a-glance** for parents: what's coming, what's due, what's for lunch
3. **Fun for kids:** countdown to breaks, weather icons, maybe lunch "stars" or theme days
4. **Self-updating:** agent-driven pipeline pulls from sources on a schedule; nobody maintains it by hand
5. Low cost to run, low complexity to host

## 2. Information Sources (4 confirmed)

| # | Source | Content | Access method (TBD) | Update cadence |
|---|--------|---------|--------------------|----------------|
| 1 | **WhatsApp groups** (2) | Announcements, last-minute changes, event reminders, for-sale items | ✅ SOLVED: Gveld logs to markdown files on SynologyDrive (`projects/whatsapp/whatsapp-salmon-creek.md`, `whatsapp-harmony-sc-free-trade-sell.md`). Format: `[YYYY-MM-DD HH:MM] [group] Sender: text` — **scanner 2x daily** (tail-read, relevance filter) feeds community-feed.json | 2x daily |
| 2 | **School website** | Official calendar, events, policy notices | Web fetch/scrape — needs URL + structure survey | Daily |
| 3 | **School emails** | Newsletters, teacher comms, forms | Gmail (gog CLI already authed) — needs label/filter rule ("school" label) | On arrival |
| 4 | **ParentSquare app** | Official announcements, alerts, sign-ups, calendar | ✅ TWO channels confirmed: (1) **Email digest** — arrives daily to sorenandkenzo@gmail.com from `donotreply+...@parentsquare.com` (verified Sep 2/Aug 26 digests; parseable format, includes event posts); needs Gmail filter/label + forward rule to Artemis inbox. (2) **iCal feed** — proven live. Digest = notices; iCal = calendar | Daily (digest) + on fetch (iCal) |
| 5 | **shARK Foundation** (harmonyark.org) | School foundation events (Glow Party, Autumn Gather, Move-a-thon...), annual campaign, volunteer calls | Web fetch of harmonyark.org — event dates structured enough to parse; volunteer/pledge info is static-ish. Source for the shARK card + its events merge into the calendar | Weekly |

### Derived data (computed, not sourced)
- **Countdowns:** to breaks/holidays (source: calendar events)
- **Weather:** local forecast (Open-Meteo API — free, no key)
- **Lunch menu by day:** from wherever menus are posted (website? ParentSquare? PDF?) — NEED SOURCE

## 3. Open Questions (need answers before build)

1. **ParentSquare:** does it offer email digests? If yes, email pipeline covers it and we skip app integration entirely (preferred). Does Rachel/Kenzo have admin visibility?
2. **Lunch menu source:** where do menus actually live? Website page? PDF? ParentSquare post? Monthly or weekly?
3. ~~**WhatsApp → Gveld pipeline:** what format does Gveld's tracking produce?~~ **ANSWERED 2026-09-03:** markdown logs at `C:\Users\kenzo\SynologyDrive\projects\whatsapp\`, format `[YYYY-MM-DD HH:MM] [group] Sender: text`. Collector = hourly tail + regex. Note: these are raw chat logs (chatter included) — collector needs relevance filtering (keywords: no school, reminder, due, event, date, forms, early release, etc.) to separate announcements from conversation.
4. **Audience/access:** who views this? Family-only (auth) or shareable link? Kids' devices?
5. **School identity:** which school/site URL? Which WhatsApp group(s) are official vs parent-chat noise?
6. **Display target:** browser tab on a wall tablet / family PC / phones? Responsive or fixed?

## 4. Pipeline Architecture (conceptual)

```
[Sources]                  [Collectors]           [Store]            [Render]
WhatsApp groups  ──────►  2x-daily scanner  ──┐
School website   ──────►  daily fetcher    ──┼──►  events.json    ──►  git push ──► Vercel
School emails    ──────►  Gmail watcher    ─┤      menu.json            (auto-deploy
ParentSquare     ──────►  digest + iCal    ────►   notices.json           on push,
Weather API      ──────►  daily fetch      ────►  weather.json           ~30s)
```

**Deploy model (added 2026-09-03):** Vercel watches the GitHub repo; every git push triggers auto-deploy (~30s). Scanner crons end with commit+push — commit message doubles as changelog. Deploy Hook URL available as manual escape hatch. Site always serves the latest deploy; worst-case staleness = hours since last scan + deploy time.

**Principles:**
- Collectors normalize everything into a small set of JSON files: `events.json`, `notices.json`, `menu.json`, `weather.json`
- Store is plain files (git-versioned in this repo) — no database, trivially debuggable
- Each source has its own collector; a broken source degrades one widget, not the site
- Agent (Artemis) runs collectors on schedule (cron) and can also be told "add this event" conversationally as a fallback

### 4.1 Normalization schema (draft)

```json
// events.json
{ "events": [
  { "date": "2026-09-25", "title": "Harvest Festival", "source": "website",
    "kind": "event", "allDay": true } ] }

// notices.json
{ "notices": [
  { "posted": "2026-09-03", "title": "Picture day forms due", "source": "whatsapp",
    "urgency": "normal", "text": "..." } ] }

// menu.json
{ "menu": { "2026-09-08": {"lunch": "Pizza", "alternates": ["Salad"]}, ... } }
```

## 5. Display / Dashboard Design (conceptual)

**Layout (single page, big-type, kid-friendly):**
- **Hero strip:** today's date, weather icon + temp, countdown chip ("🍂 Fall Break: 12 days")
- **This Week:** upcoming events list (next 7-14 days), color-coded by kind
- **Lunch:** today's menu big; week view available; kid-friendly icons per meal type
- **Notices:** latest announcements (deduped across sources), newest first
- **Fun:** rotating kid touches — countdown emojis, season art, "days until summer" always visible

**Tech direction (decide later, candidates):**
- Static site generator or single HTML+JS reading the JSON files — simple, fast, hostable anywhere
- Auto-refresh (polls JSON every N minutes on wall displays)
- Host: local (family devices on LAN) or free static host if shareable link wanted

## 6. Build Phases

| Phase | Deliverable | Depends on |
|-------|-------------|-----------|
| **0. Survey** | Answer open questions (§3): source URLs, menu location, ParentSquare digest?, Gveld handoff format | Kenzo/Rachel + Gveld |
| **1. Weather + Countdown spine** | Static page w/ weather + break countdown from hard-coded dates — visible win, no pipeline yet | nothing |
| **2. Calendar pipeline** | Website scrape → events.json → This Week widget | School website URL |
| **3. Email pipeline** | Gmail label → notices.json | Gmail filter rule |
| **4. WhatsApp pipeline** | Gveld capture → notices.json | Gveld format |
| **5. Menu pipeline** | LINQ API (SOLVED 2026-09-03) | ✅ endpoint captured |
| **6. Polish** | Kid theme, icons, wall-display mode | Phases 1-5 |
| **7. Deploy pipeline** | Git repo → Vercel (auto-deploy on push); scanner cron ends with commit+push | Phases 1-5 |

## 8. Design Handoff (for Claude — design system + mockups)

**Task for the designer:** produce a design system (colors, typography, spacing, iconography) and 2-3 layout mockups for a single-page family dashboard. Playful but readable; kids should like it, parents should trust it.

**Content the design must accommodate — FRONT PAGE = TODAY (Kenzo, priority directive):**
The main/first screen is **Today**: what's happening today, not a planning view.
1. **Hero (Today):** today's date, large · weather (icon + temp + hi/lo) · **TODAY'S LUNCH** prominent (main + sides + alternates) — if no school today, say so instead
2. **Today's schedule items:** anything on the calendar TODAY (early release, conference, event) — big and unmissable
3. **Countdown chip:** one prominent chip — next break/last day ("🍂 Fall Break: 12 days")
4. **Coming up:** only the next few scheduled items (next 7 days), secondary to Today — **includes shARK events** (Glow Party Sep 18, Autumn Gather Oct 3, Move-a-thon Nov 13, etc.)
5. **Notices:** latest announcements, newest first
5b. **Community feed + digest (Kenzo, added Sep 3; cadence raised Sep 3):** TWO layers from the same scans:
  - **Community feed (near-live):** scanner runs 2x daily (morning + evening), tails Gveld's logs, filters signal (announcements, events, for-sale, road alerts), writes `data/community-feed.json` — recent notable items + active For Sale listings (item, price, who; auto-expire >14 days) + last-updated timestamp. Site renders it fresh on every load; this is the close-to-live pulse.
  - **Weekly digest:** Artemis-written summary 1-2x/week (notable chatter + highlights), `data/community-digest.json`, rendered as the summary card. NOT raw chat lines.
  - Both generated from the same scan; digest is the human summary, feed is the item-level pulse.
5c. **shARK card (Kenzo, added Sep 3):** dedicated card lower on the page linking to harmonyark.org with a blurb and "Let's help shARK help our school" CTA. Content: next upcoming shARK event + one-line campaign note ($75K goal, funds garden/theater/library). Events from shARK also merge into the main calendar/Coming-up (double-listing is fine: calendar for schedule, card for identity/support).
6. **Get Involved (submission links):** student "Submit news or editorials" + parent "Suggest an event" as mailto links — visible but not competing with Today info (footer or slim strip)
7. **Sponsor banner:** reserved slot on front page (below hero or footer) for local-business sponsors; kid-page-appropriate, no popups/tracking
8. **Fun layer:** kid-friendly icons, season art — but Today-first information hierarchy

**Design note — footer zone:** in at least one mockup, treat the sponsor banner + Get Involved strip as a single combined footer zone. This keeps the Today screen clean and gives the community elements (sponsorship, submissions, event suggestions) one natural home instead of competing for front-page space.

Week/month views and full calendar are secondary screens, not the front page.

**Technical constraints for the design:**
- Single page, browser-rendered, reads JSON files (no server logic in v1)
- Must work on: wall tablet (large type, glanceable), laptop browser, phone
- Auto-refreshes data every N minutes (design shouldn't assume static)
- Weather + countdowns update without page reload ideally

**Submission links (new, Kenzo):** static mailto links, no backend — student news/editorial address TBD + parent event-suggestion address TBD (suggest creating these inboxes). If the school later wants real forms, v2 item.

**Sponsor banner (new, Kenzo):** data-driven slot — `data/sponsors.json` ({name, image?, link?, active}) so Artemis updates sponsors without touching layout. Design defines slot style/placement.

**Data shapes available (exact JSON the design will bind to):**
- `data/menu-and-events.json` — daily lunch menu (main/sides/options/milk), breakfast weekly rotation, ParentSquare events
- `data/calendar-year.json` — 19 school-year dates: breaks w/ ranges, holidays, conferences, early releases, first/last day
- `data/parentsquare-live.ics` — live iCal feed (auto-fetched hourly)
- `data/notices.json` — WhatsApp/email/ParentSquare notices (planned)
- `data/sponsors.json` — sponsor banner entries (planned)
- Weather: Open-Meteo (icon codes available)

**Brand anchors:** school is Harmony Union SD (Occidental, west Sonoma County) — environmental/outdoor education identity (garden, composting, watershed). Earthy palette could work; so could bright kid-primary. Designer's call — show us.

**Deliverable back to Artemis:** design tokens (colors/type/spacing as values), layout wireframes/mockups per breakpoint (tablet/phone/laptop), and component notes per widget. Artemis implements against the live JSON contracts.

## 9. Decisions Log

- 2026-09-03: Project started. Spec phase, no code. Folder: `C:\dev\school-dashboard`.
- 2026-09-03: All sources mapped (WhatsApp logs solved via Gveld; ParentSquare iCal feed proven live; LINQ menu = JS app, endpoint capture pending; menu fallback = monthly PDF parse). Data JSONs built from real PDFs.
- 2026-09-03: Design to be done by Claude (external) — handoff brief in §8. Artemis implements after design returns.
- 2026-09-03: LINQ menu API SOLVED — `https://api.linqconnect.com/api/FamilyMenu?buildingId=c6b2e3f4-82bd-ef11-8321-e7236f8c8a07&districtId=34ae3846-e8b0-ef11-8321-94f035f3f81f&startDate=M-D-YYYY&endDate=M-D-YYYY` (requires Origin/Referer/UA browser headers; returns structured JSON with categories, recipes, nutrition, allergens; rolling date window params). ALL SOURCES NOW AUTOMATED — zero manual fallbacks. BUILD-READY.
