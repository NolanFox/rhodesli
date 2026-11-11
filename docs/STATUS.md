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
- **Supabase:** see "Prior work via ChatGPT — October 2026" below. The
  October history (recovered 2026-11-02) leaves this open: a paid
  "Nolan Fox Projects" organization ($27.09/mo, renewing ~2026-11-11)
  still to locate and decide on, and a separate Free-org project found
  paused. _Findings: in that section._
- **Cloudflare R2:** bucket costs, plus registrar/renewal status for the
  `nolanandrewfox.com` domain. _Findings: pending._

### Usage analysis — in progress (2026-11-02)

To answer "who has been using the site, and how," a PostHog usage audit and
expanded Supabase (auth users + table activity) and Railway (traffic / last
deploy) checks were launched 2026-11-02. _Findings: pending._

## Prior work via ChatGPT — October 2026 (recovered 2026-11-02; not previously committed)

- **Source:** Nolan's ChatGPT conversation "Rhodesli Restart Review"
  (messages 2026-10-15 and 2026-10-19), reviewed read-only on 2026-11-02.
  In those chats, "DotBot" names the site's face-recognition service role;
  "Dots" is a separate ChatGPT launcher (GPT-6 Astra) from a 2026-10-09
  chat that set the rules "GitHub is the source of truth; log every
  finished task to GitHub." This October work had NOT been logged to
  GitHub — this section is that log, added after the fact.
- **Baseline found 2026-10-15:** Railway + Supabase baseline was
  $46.27/month. Railway payments had risen through 2026 (May $14.20,
  June $11.00, July $9.60, August $10.64, September $18.02, October
  $19.18). The Supabase paid subscription was $27.09/month (invoices paid
  2026-09-11 and 2026-10-11 — verified from Gmail on 2026-11-02; next
  expected ~2026-11-11).
- **Changes executed 2026-10-15 (Railway only,** by the ChatGPT assistant
  with Nolan's integrations connected): enabled serverless mode on both
  Railway services (the rhodesli website and ml-service); set
  `PROCESSING_ENABLED=false` on the website; replaced a previously
  exposed ml-service credential in both services. Result: website memory
  dropped from 1.96 GB to 0.39 GB (~80% reduction), and both deployments
  stayed online. It explicitly did NOT delete services, remove the
  Railway volume, alter the database, or change the Supabase plan.
- **Verification 2026-10-19:** serverless is enabled, but the services
  were NOT actually sleeping, because the site receives heavy crawler
  traffic — 44,471 requests in 72 hours (30,856 in 24 hours), with 196
  of 201 sampled requests identifying as GPTBot, crawling public
  family-tree/map/timeline routes (robots.txt allows it). Estimated
  potential RAM savings ~$10.50/month — an estimate, NOT a verified
  billing reduction.
- **Supabase state (important, unresolved):** June 2026 work had reduced
  the database from ~1.3 GB to 244 MB, making the Free plan plausible,
  but (a) the size was never re-confirmed below 500 MB after June,
  (b) free-tier projects auto-pause after inactivity — a risk flagged on
  2026-10-15 — and (c) NO downgrade was ever executed in ChatGPT. The
  $27.09 paid subscription belongs to an organization the chats call
  "Nolan Fox Projects"; the Supabase organization reachable via Nolan's
  GitHub sign-in is a DIFFERENT, Free organization. On 2026-11-02 that
  Free org's project "Rhodesli Production" (ref `zdixmiapfjordmplyfvx`,
  us-east-1) was found PAUSED with zero current-period usage — consistent
  with the free-tier inactivity auto-pause. **Open items:** (1) locate /
  sign in to the paid "Nolan Fox Projects" org and decide on the $27.09
  subscription before its ~2026-11-11 renewal; (2) decide whether to
  restore the paused Free-org project (needed to inspect users/tables
  and the true database size).
- **Gemini note from the same chat:** a Google notice requires prepaid
  billing for paid Gemini API usage beginning 2026-10-12; the
  recommendation recorded there was to keep auto-recharge disabled while
  not using paid Gemini features.
- **Follow-ups the ChatGPT side had scheduled:** a recurring monthly
  cost audit (next 2026-11-09) and a "Rhodesli Restart Review —
  2026-12-10" restart decision.

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

## Update — 2026-11-11 (Zorro): Supabase downgrade executed; spend drawn down

**Decision (Nolan, 2026-11-11):** draw Rhodesli expenses down until the
Buki AI project is finished and Rhodesli is revisited properly. Spend can
go back up later. The Dec 10 restart review stands.

**The downgrade is now DONE.** Background: the move to Free was decided
in June 2026 (database shrunk ~1.3 GB to ~244 MB to fit the Free plan)
and researched/recommended by ChatGPT on 2026-10-15, but never executed
— confirmed 2026-11-11 from three sources: this doc, the ChatGPT
'Rhodesli Restart Review' thread (it states it made zero Supabase
mutations in October), and Zorro's live inventory below.

**Inventory (Zorro, read-only, 2026-11-11):** org 'Nolan Fox Projects'
was on Pro, projected $27.09/mo. Projects: 'rhodesli' (us-west-2,
ACTIVE; database 259.9 MB, storage 0 — this is the live site's
database) and 'NolanFox's Project' (PAUSED; size not measurable while
paused; data stated safe by Supabase). November invoice SWYQUK-00014,
$27.09, was issued and PAID on 2026-11-10 — the downgrade did not beat
that charge. The downgrade flow stated the unused remainder of the
cycle would be refunded as credits (amount not shown at the time).

**Action (Zorro, on Nolan's explicit approval, 2026-11-11 ~12:23 PM
ET):** downgraded 'Nolan Fox Projects' from Pro to Free. Nolan cleared
the sign-in hCaptcha himself; no other sign-in or spend by anyone.
Verified after: plan shows Free, current and projected costs $0.00,
no upcoming invoice; 'rhodesli' active, 'NolanFox's Project' still
paused; Free usage 273/500 MB database, 0/1 GB storage. No warning in
the flow mentioned data deletion. Free-tier caveat now in force:
projects pause after 1 week of inactivity.

**Not done, by Nolan's decision (2026-11-11):** no Gemini top-up.
Face-matching stays down (prepaid credits depleted; Google spend is
effectively $0) until the restart review. A help form on the upload
path, so visitors can report breakage, is to be added — responses are
the signal for possibly re-enabling face-matching.

**Attribution:** October 2026 infrastructure changes (Railway
serverless, processing flag, credential replacement) were ChatGPT's;
its Supabase work was read-only. The Nov 2 cost audit, the Nov 11
inventory and downgrade, and this entry are Zorro's. All approvals and
the CAPTCHA were Nolan's.
