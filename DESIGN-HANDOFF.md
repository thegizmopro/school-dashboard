# School Dashboard — Design Handoff for Claude

**Project:** Family dashboard for Harmony Union School District (Occidental, CA — small west-Sonoma community school, K-8, place-based environmental education identity: redwoods, garden, watershed).
**Audience texture:** ~163-family community, lots of Airbnbs and year-round coastal visitors. Kids K-8, parents on phones, a wall tablet in the kitchen planned. Playful enough for kids to like it, clean enough that parents trust it.

---

## Your task

Produce:
1. **A design system** — colors, typography, spacing scale, iconography direction (as concrete values/tokens)
2. **2–3 layout mockups** — at minimum: wall-tablet/large view, laptop browser, phone. At least one mockup must use the combined footer zone (see below)
3. **Component notes** per widget — what each looks like, how data appears, states worth designing (e.g., "No School today", empty notice list)

This is a single-page family dashboard. **The front page is TODAY** — what's happening today, not a planning view. Week/month views are secondary screens.

---

## Front-page content (priority order)

1. **Hero (Today):** today's date, large · weather (icon + temp + hi/lo) · **TODAY'S LUNCH** prominent — main entrée, sides, daily alternates (yogurt parfait / SunButter jam sandwich), milk choices. If no school today, that replaces lunch.
2. **Today's schedule:** anything on the calendar TODAY (early release 1:10pm, conference, event) — big and unmissable.
3. **Countdown chip:** one prominent chip — next break/last day ("🍂 Winter Break: 109 days").
4. **Coming Up:** next ~7 days of scheduled items only, secondary to Today. Color-coded by kind (holiday / break / conference / event / no-school).
5. **Notices:** latest announcements, newest first, source-tagged.
6. **Community feed:** near-live pulse from the school's WhatsApp groups (2× daily scan) — recent notable items + a **For Sale / Free** list from the community trade group (item, price, who; listings expire after 14 days).
7. **Get Involved strip:** student "Submit news or editorials" + parent "Suggest an event" — mailto links, visible but not competing with Today info.
8. **Sponsor banner:** reserved slot for local-business sponsors (rotating via JSON; kid-page-appropriate, no popups/tracking).
9. **shARK card (lower page):** the parent foundation's card — blurb, next shARK event, one-line campaign note ($75K goal funds garden/theater/library), CTA "Let's help shARK help our school" → harmonyark.org.

**Design note — footer zone:** in at least one mockup, combine the sponsor banner + Get Involved strip into a single footer zone. Keeps the Today screen clean; gives community elements one natural home.

**Fun layer:** kid-friendly icons, season art, occasional whimsy — but Today-first information hierarchy wins ties.

---

## Real data the design binds to (current, September 2026)

**Today's lunch example (Sept 3):** Pesto Pasta · Cottage cheese · Apple · Salad bar · Celery. Alternates every day: Yogurt & seasonal fruit parfait OR SunButter & jam brown-bag. Milk: 1% or nonfat chocolate. **Pizza Friday** is house-made (Dos Pisano's) — worth a visual celebration.

**Coming Up (real, next ~2 weeks):**
- Sep 10 — HUSD Board Meeting, 6pm
- Sep 11 — Parenting Through Adversity workshop, 8:30am, library
- Sep 18 — **Glow Party** (shARK: family dance, DJ, black lights, glow sticks), 6–9pm — same day as grant deadline (coincidence, different projects)
- Sep 25 — Pumpkin Patch pop-up (Daisy Bakery attendance)

**Countdown targets:** Labor Day No School (Sep 7, imminent) → Winter Break (Dec 21) → Last Day of School (Jun 2, 2027).

**Notices (typical density):** 1–3/week. Real examples: "Hand In Hand Parenting Workshops starting October 14th" (5-week class, Salmon Creek parents); consent-form reminders.

**For Sale / Free (typical density):** a handful of listings — item, price, poster.

**shARK campaign line:** "Last year this community raised $75,000 — $50K straight to the school, the rest to events, classroom requests, and staff appreciation."

---

## Technical constraints

- **Single page**, browser-rendered, reads JSON files via fetch (no server logic in v1)
- **Breakpoints:** wall tablet (large type, glanceable, landscape), laptop browser, phone (stack)
- **Auto-refresh:** data fetches every N minutes; design shouldn't assume static
- Weather + countdowns ideally update without full reload
- Static mailto links for submissions (no forms/backend in v1)
- Deploy: static hosting (Vercel), auto-deploys on data commits

## Data files the design binds to (attached)

1. `menu-and-events.json` — September lunch menu (main/sides/options/milk per day), breakfast weekly rotation, ParentSquare events
2. `calendar-year.json` — 19 school-year dates: breaks with ranges, holidays, conference weeks, early releases, first/last day
3. `parentsquare-live.ics` — the live iCal feed (fetched hourly; currently 3 events, grows with the year)
4. `linq-menu-sample2.json` — raw LINQ API sample showing the live menu feed structure (22 lunch days, breakfast + lunch sessions, categories/recipes/nutrition)
5. `notices.json` — planned shape: [{posted, title, source, urgency, text}]
6. `community-feed.json` — planned shape: [{scanned, items: [{date, group, sender, text, kind}], listings: [{item, price, who, posted}]}]
7. `sponsors.json` — planned shape: [{name, image?, link?, active}]

---

## What we need back

- Design tokens (colors as values, type stack/scale, spacing scale, icon set recommendation)
- Mockups: wall-tablet, laptop, phone (at least one showing the combined footer zone)
- Per-widget component notes: content layout, data binding points, states ("No School today", empty feed, stale listing)
- Any motion/refresh notes (what pulses, what's static)
