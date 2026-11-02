# Rhodesli — Project Status

**Last updated: 2026-11-02**

This document is the current state of the project in one place, so work can
pick back up cleanly. It records where things stand, what the open items are,
and what was decided most recently.

## What Rhodesli is

Rhodesli is a photo-identification site for Rhodes Jewish heritage: visitors
browse historical community photos and help identify the people in them.

- Live at: https://rhodesli.nolanandrewfox.com
- Size as of 2026-10-15: 2,132 photos / 1,816 people

## Stack

- **App:** FastHTML + HTMX, deployed on Railway (`railway.toml` + `Dockerfile`).
  Deploys happen via `git push origin main`.
- **Database & auth:** Supabase (Postgres + auth).
- **Photo storage:** Cloudflare R2, bucket `rhodesli-photos`.
- **Face matching:** Gemini API generates ML face-matching proposals;
  InsightFace runs on Nolan's own compute.
- **Analytics:** PostHog, wired in server-side (`app/main.py` initializes
  PostHog with the `POSTHOG_API_KEY` env var, host `us.i.posthog.com`;
  capture calls live in `app/compare_routes.py` and `app/identity_routes.py`).
  PostHog is the place to see who uses the site and how.

## Current status (2026-11-02)

- The site is **live** and in regular light use.
- Nolan is **not actively developing** it right now, but plans to return to
  it soon.
- **Standing decision (2026-11-02): keep the site live and cut what's safe on
  costs. Do not park or pause it.**
- Development history in this repo: `SESSION_LOG.md` shows the last logged
  dev session was **Session 114 on 2026-03-17 (v0.99.23)**. Logged
  development sessions end there; live usage continued afterwards.

## Cost audit (2026-11-02)

### Gemini API — verified

The recurring Google Cloud charge that prompted this audit is Gemini API
usage in the Google Cloud project **"rhodesli"** (project ID
`gen-lang-client-0267455491`, billing account `01A35F-06354C-0FC466`),
charged to Nolan's Capital One Venture Visa ending 4699. It is metered
per-request billing, not a subscription.

Monthly timeline (usage month → amount paid on the 1st of the following
month; verified from Gmail receipts and the Cloud Console):

| Usage month | Paid | Amount |
|---|---|---|
| May 2026 | Jun 1, 2026 | $0.27 |
| June 2026 | Jul 1, 2026 | $1.28 |
| July 2026 | Aug 1, 2026 | $0.40 |
| August 2026 | Sep 1, 2026 | $0.51 |
| September 2026 | Oct 1, 2026 | $0.46 (usage $0.50 − $0.04 savings) |
| October 2026 | Nov 1, 2026 | $0.49 |

Baseline is a steady ~$0.40–0.51/month, with June 2026 the heaviest month at
roughly 3× baseline — consistent with a live site in regular light use, not
with anything anomalous.

A **budget alert** on the Google Cloud account has been proposed as a
guardrail against surprise usage. Not yet set.

### Railway / Supabase / Cloudflare — AUDIT PENDING

Read-only audits of the following were launched 2026-11-02; findings to be
filled in here when they land:

- **Railway:** plan and current usage/spend. _Findings: pending._
- **Supabase:** current plan tier and database size (see the tier question
  under Known flags). _Findings: pending._
- **Cloudflare R2:** bucket costs, plus registrar/renewal status for the
  `nolanandrewfox.com` domain. _Findings: pending._

### Usage analysis — in progress (2026-11-02)

To answer "who has been using the site, and how," a PostHog usage audit and
expanded Supabase (auth users + table activity) and Railway (traffic / last
deploy) checks were launched 2026-11-02. _Findings: pending._

## Security — open item

Railway disclosed unauthorized access to encrypted environment variables
between 2026-10-20 and 2026-10-22 (UTC). This workspace's env vars — a Gemini
API key, Supabase/Postgres credentials, and Cloudflare R2 tokens — matched
the pattern the attacker was searching for, and Railway could not confirm
whether they were accessed. (No credential values are recorded in this
document, by design.)

Advice given 2026-10-24:

1. Rotate the Gemini API key first.
2. Then rotate the Supabase password and the R2 tokens.
3. Check usage/audit logs at each provider.
4. Update the Railway variables and redeploy.

**As of 2026-11-02, rotation is NOT confirmed done. The decision is
Nolan's and is still pending.**

## Known flags

- **r2.dev URL:** photos currently serve from the public dev URL
  `pub-fdd617958ee1449293c7b5f8750da289.r2.dev`. Cloudflare can disable
  r2.dev URLs; suggested hardening is a custom domain such as
  `media.rhodesli.nolanandrewfox.com` via CNAME.
- **Supabase tier:** free tier allows ~500 MB of database; Pro is $25/mo.
  Which tier this project is on is part of the pending audit above.
- **Domain:** registrar and renewal for `nolanandrewfox.com` to be confirmed
  in the pending Cloudflare audit.

## When you come back

In order:

1. **Credential rotation decision** — rotate the Gemini API key, Supabase
   password, and R2 tokens per the security item above, or explicitly
   decide not to.
2. **Cost audit findings** — fill in the Railway / Supabase / Cloudflare
   results above, then approve or reject each proposed cost cut
   individually, under the standing "keep it live, cut what's safe"
   decision.
3. **r2.dev hardening** — move photo serving to a custom domain
   (e.g. `media.rhodesli.nolanandrewfox.com`).
4. **Resume development** — pick up from the Session 114 state recorded in
   `SESSION_LOG.md`, with the usage analysis (PostHog / Supabase / Railway)
   as input on what to build next.
