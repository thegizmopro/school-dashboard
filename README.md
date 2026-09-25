# Harmony Today — HUSD Family Dashboard

A single-page, auto-updating dashboard for a West Sonoma County school family:
today's lunch (with next school day's tease), the full district calendar, live
weather, community WhatsApp highlights, notices, and shARK Foundation events.
Kid-friendly, parent-trusted, installable to phone home screens.

**Live:** `https://harmony.justsoyouknow.site` (Vercel — the only deploy target)
**Status:** in production since Sep 2026; data pipeline self-updates 4×/day.

```
[WhatsApp groups]──┐                                   ┌─ collectors/collector.py (cron 4x/day)
[ParentSquare ics]─┤                                   │   writes site/data/*.json + local data/
[District website]─┼─► collectors (python, cron) ──►  │   + regenerates all-events.ics
[harmonyark.org]───┤                                   │
[LINQ menu API]────┤                                   └─ collectors/gen_digest.py (agent cron 6:45am)
[Open-Meteo]───────┘                                        writes site/data/community-digest.json
        │
        ▼  git commit + push (crons do this themselves)
   Vercel auto-deploy (~30s) ──► site/index.html reads site/data/*.json client-side
                              ──► api/submit.js (forms → email via Resend)
```

## Repo layout

| Path | What it is |
|---|---|
| `site/index.html` | The whole site: one HTML file, embedded CSS + JS. No framework, no build step. |
| `site/data/` | **Published data contracts** (see table below). Everything here deploys publicly. |
| `site/sponsors/` | Sponsor images (processed copies; drop originals in `sponsors/` + run installer). |
| `api/submit.js` | Vercel serverless function: student-news / event-suggestion forms → email (Resend). |
| `collectors/collector.py` | Main collector: WhatsApp scan, iCal, district calendar, shARK scrape, board-meeting link, weather, LINQ menu, merged calendar feed. |
| `collectors/gen_digest.py` | Community digest: dry-run default, `--write` publishes (merge semantics, see its docstring). |
| `collectors/local-config.json` | **Local, gitignored** — ParentSquare feed URL (private token) + WhatsApp log paths. See `local-config.example.json`. |
| `collectors/scan-state.json` | WhatsApp scan position — local, gitignored. |
| `sponsors/` | Drop folder for new sponsor images + `install.py` (normalizes, deploys, updates JSON). |
| `data/` | **Local-only pipeline state** (raw WhatsApp feed/items). Gitignored. Never deploys. |
| `instructions.md` | Private operator notes (manual digest refresh etc.). Gitignored, local machine only. |
| `CRONS.md` | **The automation reference** — schedules, OpenClaw ids, prompts, safety rails. Read this for ops. |
| `SPEC.md` | Original 2026-09-03 spec — historical record only, predates most of the system. |
| `DESIGN-SYSTEM.md`, `DESIGN-HANDOFF.md`, `handoff/` | Design tokens (incl. `tokens-dark.json`) and the original mockups. |

## Data contracts (`site/data/`)

| File | Written by | Read by | Refresh |
|---|---|---|---|
| `weather.json` | collector | site (fallback; the page also calls Open-Meteo directly each 5-min render) | 4×/day |
| `parentsquare-live.ics` | collector (ParentSquare feed) | site events card, merged ics | 4×/day |
| `district-calendar.ics` | collector (harmonyusd.org master calendar — authoritative events layer) | site events card, merged ics | 4×/day |
| `board.json` | collector (scrapes the live board-meeting link off the district homepage) | board-meeting rows + ics URLs | 4×/day |
| `shark.json` | collector (harmonyark.org — tiered scraper; the site rebuilt to Next.js ~Sep 16) | shARK card, events card, ics | ~weekly (staleness-gated) |
| `menu-linq.json` | collector (LINQ API, 45-day window) | lunch card (primary source) + week dialog | ~daily (staleness-gated) |
| `calendar-year.json` | hand-curated from the district PDF | structural layer: no-school map, break ranges, countdown | rarely (school year) |
| `menu-and-events.json` | hand-built from September PDF | lunch fallback, breakfast weekly rotation, daily alternates | as needed |
| `notices.json` | **agent-curated from ParentSquare emails** (manual/agent pass — not a cron yet). Rows carry an optional `until` date; the site hides expired ones. Never store email click-tracking URLs — use the real destination. | notices card | on email arrival |
| `community-digest.json` | digest cron 6:45am (agent-written prose + merged listings) or manual `--write` | community card | daily |
| `all-events.ics` | collector (merged: structural + shARK + notices + ParentSquare + district, canonical-title dedupe, stable UIDs, board-meeting URLs) | calendar subscription link | 4×/day |
| `sponsors.json` | `sponsors/install.py` or by hand | sponsor tiles | on change |

## How the site works (one file, ~750 lines)

- **Render loop:** every function re-renders on a 5-minute interval (`renderAll`) —
  wall tablets stay open for days; everything rolls over. All data fetches are
  cache-busted (`?t=`).
- **Events precedence & dedupe:** four sources merge — shARK (curated/linked) →
  ParentSquare (near-term) → structural calendar (styled no-school rows) →
  district master calendar (everything else). Same-date events collapse via
  `canonTitle()` families ("Harvest Gather TBD" == "Autumn Gather"); district
  no-school entries on structural dates are suppressed.
- **Lunch:** LINQ live menu is primary, PDF-derived fallback; hot main picked by
  excluding published alternates; LINQ kitchen shorthand humanized
  ("House-made Dos Pisano's pizza"); tomorrow tease skips weekends/holidays;
  `week's menus →` dialog shows Mon–Fri breakfast+lunch.
- **Trusted vs untrusted HTML:** digest prose renders as HTML (it is agent-written,
  with auto-close for unclosed anchors); everything scraped/chat-derived is
  escaped or linked through `esc()`/`link()` with http(s)-only URLs.
- **Forms:** two dialogs POST to `/api/submit` (honeypot, graceful unwired state).
- **PWA:** manifest (standable), apple-touch-icon + favicon, theme-color.

## Environment variables (Vercel, production)

| Var | Purpose |
|---|---|
| `RESEND_API_KEY` or `RESEND_KEY` | Resend API key (either name accepted) |
| `SUBMIT_TO` | inbox receiving form submissions |
| `SUBMIT_FROM` | sender on the verified resend domain (`harmony@justsoyouknow.site`) |

No vars → `/api/submit` returns 503 with a friendly "not wired" message. Env var
changes require a redeploy to take effect.

## Privacy boundary — the one rule that matters

**Everything under `site/` deploys publicly.** Raw WhatsApp content (real names,
chat text) must only ever live in root `data/` (gitignored). The collector writes
`community-feed.json`/`community-items.json` there, never into `site/data/`.
Published listings carry **no `who` field** (stripped at publish) and are
paraphrased by the 6:45 agent; the digest prose is sanitized at render to an
allowlist (https anchors + basic formatting only) with a CSP on top — chat-steered
HTML cannot execute. The ParentSquare feed token lives in
`collectors/local-config.json`, gitignored.

## Working on this repo

- **Deploy = `git push`** (Vercel). Crons commit+push themselves; their commits
  ("scan …", "digest …") are normal history.
- **Testing pattern:** no framework — syntax-check extracted JS with
  `node --check`, drive page functions in a `node` VM with DOM/fetch stubs and
  fake `Date`s, serve `site/` with `python -m http.server` and check in a browser.
- **Digest guards are structural:** `--write` rejects empty/over-long/unbalanced-anchor
  prose; listings merge (never replace); expiry is 5 days.
- **SOURCES CHANGE SHAPE.** harmonyark.org rebuilt once already; the scraper is
  tiered (embedded JSON → rendered list → bare headings) and empty states are
  deliberate so breakage is visible, not silent.
- Ops lives in **CRONS.md**; manual runbook in local **instructions.md**.
