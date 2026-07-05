# Multi-Tenant Readiness Assessment (2026-07-05)

**Verdict: community-aware, not tenant-safe — and the live site now *shows* the gap, not just the
code.** Both prior drafts reached this conclusion from code; this run confirms it from the rendered
product and adds one major surface neither draft found (the Tree). Concierge pilot with 1-3 known
families is the right posture; broad self-service is 2 layers of work away.

## What genuinely exists (verified)
- `/c/<slug>/` routing with explicit-community 404s (`CommunityMiddleware`, `app/main.py:755-815`).
- Join-table scoping (`photo_communities`, `identity_communities`) with fail-closed photo/identity
  set loading since Session 169 (`app/main.py:884-1022`).
- Per-archive landing pages with scoped stats/CTAs; neutral platform root (`app/page_routes.py:582-840`).
- Self-service archive creation, flag-OFF, with owner_id/privacy/r2_prefix fields, IP throttle,
  per-user cap, fail-closed load, real tests (`app/onboarding_routes.py`, verified
  `privacy="unlisted"` at :392).
- Community-scoped GEDCOM schema (composite community-scoped PKs since Session 164).

## The gap list — what breaks when family #2 arrives (each verified this run)

| # | Gap | Evidence | Blast radius for family #2 |
|---|---|---|---|
| G1 | **Global-admin-only permission model.** `_check_admin` checks `user.is_admin` from a global email list; all triage/moderation/community CRUD behind it. | `app/main.py:1972-1987` (re-read this run), `app/auth.py:33-77` | Owner can browse their archive but cannot approve/reject/ingest/triage anything — every action routes through Nolan. This is THE gate (WORKSPACE-006). |
| G2 | **Privacy stored, never enforced.** Middleware checks slug existence only; root lists ALL communities. | `app/page_routes.py:799-840` (no privacy filter — re-read); **live proof:** the Fox Family personal archive is on the public front page with counts and enter buttons (`screenshots/desktop-01-root.jpeg`) | Family #2's "unlisted" archive is publicly discoverable from day one — a betrayal of the exact privacy promise made at creation. |
| G3 | **Tree surface ignores community entirely (NEW this run).** `/api/tree/data` builds from the global GEDCOM with no community filter. | `app/page_routes.py:10939-10990`; **live proof:** `/c/rhodes/tree` renders Meyer Fox / Sadie Fox Levine / Fader / Newman (`screenshots/desktop-11-tree-loaded.jpeg`) | Family #2 uploads a GEDCOM → their ancestors appear in *every* archive's tree, and Fox ancestors appear in theirs. Schema supports scoping; the reader ignores it. Audit siblings: Map, Timeline, Connect likely share the pattern (unverified — check before pilot). |
| G4 | **Moderation not archive-scoped end-to-end.** Pending metadata writes `community_id`; admin page filters `u.get("community")`; compare-created entries carry no community field at all. | `app/upload_routes.py:780-791` vs `app/admin_routes.py:565-576` (re-read); `app/compare_routes.py:1686-1700` (re-read — no community key in the dict) | Even after G1 is fixed, the owner's queue can't be correctly populated; anonymous compare junk lands in nobody's queue (today: everybody's). |
| G5 | **Storage not archive-prefixed.** Onboarding assigns `r2_prefix=archives/{slug}` but upload/compare processing writes generic `raw_photos/{filename}` / shared prefixes. | `app/onboarding_routes.py:392`, `app/upload_routes.py:982`, `app/compare_routes.py:1836` | No per-archive deletion/export story; filename collisions across families (photo IDs are SHA256 of *basename* — two families both upload `scan001.jpg`); can't ever offboard a family cleanly. |
| G6 | **Compare/contribution boundary conflated + logged-in auto-approve.** | `app/compare_routes.py:1664-1704`; full design in `SPAM_BOUNDARY_DESIGN.md` | Signup widening = archive-write widening. Must land before ANY new accounts. |
| G7 | **Cross-community bleed on shared surfaces by design.** Unprefixed `/help` mixes all communities (fail-open); cross-batch ML matching is intentionally global (`app/upload_routes.py:1115-1124`). | **live proof:** Fox Dayton + Fader faces on root /help (`screenshots/desktop-07/08`) | Family #2's unidentified relatives get shown to strangers by default, without consent language. Cross-archive matching is a *feature* for Rhodes descendants (families interlink) but needs opt-in framing. |
| G8 | **Count/identity definitions inconsistent across surfaces.** "142 people identified" vs "88 people · 87 named" on the same community. | `screenshots/desktop-02` vs `desktop-09` | Data-trust erosion for the genealogist audience; multiplies per-archive once owners can see their own numbers. |
| G9 | **Nav/copy still single-tenant in spirit.** Root copy is internal changelog-speak; person/tools nav is Rhodes-flavored regardless of entry community; three nav systems. | `screenshots/desktop-01`, `desktop-04`; F4/F6 in `UX_NEWCOMER_AUDIT.md` | Family #2's shared links render with the wrong archive identity — weakens the per-family value proposition that justifies the whole effort. |

## What I disagree with / refine from the prior drafts
- Codex's gap list is accurate but under-weights **rendered-surface leaks** (G3 tree — its
  biggest miss — plus map/timeline as unaudited siblings). Route-level scoping audits pass while a
  data-API (`/api/tree/data`) leaks everything; the pattern to institutionalize is "audit the data
  APIs the pages call, not just the page routes" (this is exactly the class the
  `route-safety-audit` skill should absorb).
- Opus's framing "flipping the flag today ships create → owner can't triage → dead end" is right
  but incomplete: even WITH triage (G1 fixed), G3+G5 mean the new family's data intermingles in
  trees and storage — "can't triage" is the first wall, "can't keep their stuff theirs" is the
  second. Both walls precede the flag flip.
- Both drafts treat privacy enforcement as a middleware feature. The live root page shows it's
  also a *copy* feature: the archive directory needs a public/unlisted split in presentation, not
  just an access check.

## Minimum safe path to the concierge pilot (flag stays OFF)
The pilot does NOT need full multi-tenancy. It needs, in order:
1. G6 defanged (ephemeral compare + no auto-approve) — before any new accounts exist.
2. G1 minimum slice: `owner_id`- or `admin_emails`-based `_check_community_admin(sess, community)`
   guard used by pending-review + upload-approve routes only (not the whole admin surface).
   The `communities.admin_emails` field already exists in the onboarding payload — the cheapest
   correct seam.
3. G4 minimum slice: every pending entry gets `community_id`; owner queue filters on it.
4. G2 minimum slice: root directory + sitemap exclude non-public archives; explicit slug access
   allowed (true "unlisted"), private = owner/admin only.
5. G3 minimum slice: tree (and map/timeline) either scoped to the community's GEDCOM/identities or
   explicitly hidden for archives without their own GEDCOM ("Tree coming soon" beats leaking the
   Fox tree).
6. Owner creates nothing self-service: Nolan creates the archive rows manually (SQL or admin UI),
   sets `admin_emails`, walks the family through upload → identify → approve on a call.
Everything else (R2 prefixes G5, storage export, contributor roles, moderation ML) can trail the
pilot by weeks without harming the first families — provided the pilot families are told, in the
invite, what's shared (cross-archive matching, root listing) until G2/G7 land.
