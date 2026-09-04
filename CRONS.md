# School Dashboard — Crons & Automation Reference

_For the developer (Claude or human). Last verified 2026-09-04._
_The scheduler lives in OpenClaw (agent "main" on this desktop), NOT in crontab or GitHub Actions._

## The one cron that matters

**Name:** `School Dashboard Collector`
**OpenClaw automation id:** `6b9607b0-29fb-484e-a0e9-7a702c78aced`
**Schedule:** `0 0,6,12,18 * * *` America/Los_Angeles (midnight, 6am, noon, 6pm; 5-min stagger)
**What it runs:**

```
cd C:\dev\school-dashboard
python collectors\collector.py
cd C:\dev\school-dashboard\site
git add data/ && git commit -m "scan <date time>" && git push
```

**Model:** zai/glm-5.3-flash (fallbacks: glm-5.2, grok-4.5) — the agent just executes the commands above; the collector itself is deterministic Python.
**Failure behavior:** agent replies with the specific error only; silent (NO_REPLY) on success.

## Collector internal tiers (as of commit c3a023c, 2026-09-03)

The collector self-tiers by STALENESS, not by clock:

| Data | Refresh rule | Output |
|---|---|---|
| WhatsApp scan | Every run (2 groups: salmon-creek, harmony-sc free-trade) | `data/community-feed.json` (LOCAL ONLY — names/chat never deploy) |
| ParentSquare iCal | Every run | `site/data/parentsquare-live.ics` |
| Weather (Open-Meteo) | Every run | `site/data/weather.json` |
| LINQ menu | When stale > 20h | `site/data/menu-linq.json` |
| shARK events | When stale > 6 days | `site/data/shark.json` |

Consequence: the "morning run does LINQ/shARK" idea from the original spec is superseded — a missed cron self-heals on the next run because staleness triggers refresh regardless of which slot it lands in.

## Deploy chain

```
collector cron → JSON updates → git add data/ + commit + push (origin/main) → GitHub Pages auto-deploy (~30s)
```

- **Hosting:** GitHub Pages at `https://thegizmopro.github.io/school-dashboard/` (workflow: `.github/workflows/deploy-pages.yml`, deploys `site/` folder only)
- **Vercel mirror exists** (`school-dashboard-zeta-ebon.vercel.app`) but GitHub Pages is the canonical link. Vercel needs Root Directory = `site` if ever revived.
- Privacy: raw WhatsApp feed is gitignored (`data/` is local-only); only derived/curated JSON deploys.

## Other scheduled jobs that touch this project

| Job | Schedule | Role |
|---|---|---|
| `gen_digest.py` (via agent, not yet its own cron) | intended 1–2×/week | writes `site/data/community-digest.json` (synopsis + For Sale/Free listings); run with `--write` to publish; dry-run default |
| Grants check (Daisy Bakery — separate but related) | Monthly, 1st @ 9am | verifies grant deadlines, emails kenbradbury@gmail.com |

## Change-history note for the dev

Commit `c3a023c` (2026-09-03, "review fixes") substantially rewrote the collector:
- weather moved to every-run; LINQ/shARK switched to staleness-based refresh
- WhatsApp feed made local-only (privacy)
- `gen_digest.py`: dry-run default, `--write` to publish, 14-day listing expiry, dedupe, URL extraction
- ICS unfold + all-day support + URL capture; HTML-escaping of collector-sourced strings
- dropped the dual GitHub Pages deploy workflow (Pages now deploys via the separate workflow file, deploys `site/` only)
- removed stray `data/system.sav`, added `.gitignore`

If the cron message text and `collector.py` docstring ever disagree, **trust the docstring** — and update the automation message.
