# Codex Draft - Security/Growth Readiness

Audience: Fable long-horizon evaluator. This is half of the brief, not a final product plan.

## Bottom Line

Rhodesli is not ready for a broad public invitation to other Rhodes-descended families or unrelated communities. It is ready for a tightly controlled concierge pilot with 1-3 known families if compare-upload is defanged first and archive ownership is handled manually by the site owner.

The app is now substantially community-aware, but not truly multi-tenant. It has `/c/<slug>/` routing, community/photo/identity join tables, community-scoped pages, and fail-closed fixes from Session 169. The missing layer is trust: per-community ownership, privacy enforcement, contribution boundaries, and abuse controls on the public face-compare path.

The new signal that changes the evaluation is the public compare tool producing ~51 anonymous "Compare Upload" pending entries. That is not just spam cleanup; it exposes a product boundary problem. A transient "compare my face" query is currently too close to a durable archive contribution.

## Evidence Commands

Representative commands used:

- `rg -n "CommunityMiddleware|community_url_prefix|_get_community_photo_ids|_get_community_identity_ids|community_id" app docs ROADMAP.md tests`
- `rg -n "WORKSPACE-|COMMUNITY-|PRD-060|SELF_SERVICE_ARCHIVE_ENABLED|create-archive" ROADMAP.md docs app tests`
- `rg -n "@rt\\(\"/api/compare|Compare Upload|pending_upload|check_rate_limit|Turnstile|captcha|recaptcha|hcaptcha" app docs tests`
- `rg -n "share|og:|help_identify|PostHog|canonical|shared-person|person/.*/photos" app docs/fable-eval docs/session_context docs/BACKLOG.md`

Notable negative result: `rg -n "Turnstile|captcha|recaptcha|hcaptcha" app tests` finds no app implementation. Mentions are docs/proposals, not runtime protection.

## 1. Multi-Community Readiness

Verdict: partially community-scoped, not safe multi-tenant.

What exists:

- Community routing is real. `CommunityMiddleware` extracts `/c/{slug}`, rewrites the internal path, defaults unprefixed public routes to `rhodes`, and 404s explicit unknown communities (`app/main.py:755-815`). Helpers know whether the community was explicit and generate `/c/<slug>` prefixes (`app/main.py:821-839`).
- Data scoping exists through join tables. Current code loads communities, photo memberships, identity memberships, and creates memberships through Supabase helpers (`app/supabase_data.py:1585-1843`). SQL scripts define `photo_communities` and `identity_communities` (`scripts/sql/session95_community_tables.sql:12-28`) and later add `owner_id`, `is_personal`, and `privacy` to communities (`scripts/sql/session_122_workspace_schema.sql:4-14`).
- Public community pages are scoped. The non-Rhodes community landing page computes stats from community photo and identity sets and offers scoped CTAs (`app/page_routes.py:582-797`). The neutral root lists communities instead of silently defaulting to Rhodes (`app/page_routes.py:799-837`).
- Some failure modes were hardened. Community photo loads avoid caching transient `None` and identity scoping fails closed if the community photo set cannot be loaded (`app/main.py:884-1022`). This backs the Session 169 note that QW-1 fixed the fail-open photos leak (`ROADMAP.md:172`).

What breaks for a second unrelated family/community:

- Permission model is still global admin. `_check_admin` only checks `user.is_admin` (`app/main.py:1972-1987`). `User.is_admin` is derived from a global email list, not community membership (`app/auth.py:33-77`), and `require_admin` is global (`app/auth.py:106-122`). Community CRUD and pending moderation are global-admin-only (`app/admin_routes.py:4512-4695`, `app/admin_routes.py:538-546`, `app/admin_routes.py:1180-1188`, `app/admin_routes.py:2195-2200`). A new archive owner cannot triage their own archive unless they are made global admin.
- The roadmap says this explicitly remains open. `WORKSPACE-006` per-community permissions is open (`ROADMAP.md:115-117`, `docs/BACKLOG.md:736-741`). PRD-036 says personal archive owners should be admins of their own archive and may promote collaborators (`docs/prds/036_workspace_onboarding.md:55-80`), but `docs/architecture/PERMISSIONS.md:1-6` still describes a binary model and says contributor/viewer roles are designed but not implemented (`docs/architecture/PERMISSIONS.md:75-77`).
- Privacy is stored but not enforced at the routing boundary. Self-service creates archives with `privacy="unlisted"` (`app/onboarding_routes.py:386-406`), but `CommunityMiddleware` only checks whether the slug exists, not privacy/access (`app/main.py:796-808`). The root loads all communities into public cards with no privacy filter visible in that handler (`app/page_routes.py:799-837`). That is unsafe for personal/private archives.
- Pending upload scoping is inconsistent. Upload metadata stores `community_id` (`app/upload_routes.py:780-791`), but the admin pending page filters by `u.get("community")` (`app/admin_routes.py:565-576`). Compare-created pending entries do not carry a community id in the same way (`app/compare_routes.py:1686-1700`). This is likely to break owner-specific moderation once more communities exist.
- R2/storage scoping does not satisfy the self-service PRD. PRD-060 requires per-archive R2 prefixes and archive-scoped data (`docs/prds/060_self_service_archive.md:108-117`, `docs/prds/060_self_service_archive.md:134-147`). Self-service creates an `r2_prefix=archives/{slug}` (`app/onboarding_routes.py:386-406`), but upload processing still writes raw photos under generic `raw_photos/{filename}` (`app/upload_routes.py:982`) and compare processing does the same (`app/compare_routes.py:1836`).
- Cross-community ML identity matching is intentionally global. Upload clustering says cross-batch matching is global because JSON lacks `identity_communities`, and notes cross-community matches are valuable (`app/upload_routes.py:1115-1124`). That can be a useful Rhodesli feature, but it needs explicit UX and consent before unrelated archives are invited.
- Architecture docs are stale enough to mislead Fable. The requested overview still says canonical data is Railway volume JSON and Postgres is planned (`docs/architecture/OVERVIEW.md:47-67`) despite CLAUDE declaring Postgres source of truth (`CLAUDE.md:19-26`) and current app code relying on Supabase community helpers. Treat docs as evidence of drift, not source-of-truth architecture.

Roadmap alignment:

- COMMUNITY-001 is marked mostly complete with remaining about/tool-picker work (`ROADMAP.md:64-65`), and the code supports that assessment for public read scoping.
- COMMUNITY-002 workspace switcher is in progress (`ROADMAP.md:66`) and code shows admin-only switching (`app/admin_routes.py:4471-4504`), not owner workspace UX.
- COMMUNITY-017 routing safety hardening is in progress (`ROADMAP.md:69`), which matches the current state: safer, but not complete.
- WORKSPACE-001 has database support for personal archives (`app/supabase_data.py:1730-1776`), but the roadmap still says redirect/upload to personal archive remains (`ROADMAP.md:109-110`).
- WORKSPACE-006 is the blocking missing layer for broad multi-community use (`ROADMAP.md:115-117`).

## 2. Onboarding / Self-Service

Verdict: a real create-archive flow exists, but it is deliberately off and not safe to enable broadly.

What exists:

- `onboarding_routes.py` implements self-service archive routes and is imported by the app (`app/main.py:8132`). The file states the write path is gated by `SELF_SERVICE_ARCHIVE_ENABLED`, default off, with permission policy deferred (`app/onboarding_routes.py:1-18`, `app/onboarding_routes.py:42-53`).
- `GET /create-archive` shows a coming-soon page when the flag is off and requires sign-in when auth is enabled (`app/onboarding_routes.py:286-306`). `POST /create-archive` is also flag-gated (`app/onboarding_routes.py:309-327`).
- The flow has basic controls: IP throttle 10/hour (`app/onboarding_routes.py:331-339`), slug/name validation and fail-closed community load (`app/onboarding_routes.py:351-368`), 3 archives per user (`app/onboarding_routes.py:371-382`), and payload fields for owner, privacy, and R2 prefix (`app/onboarding_routes.py:386-406`).
- Tests cover flag off/on behavior, blocked writes while off, happy path, fail-closed load failure, throttle, archive cap, and authenticated owner/admin payload (`tests/test_onboarding_routes.py:64-308`).

Why it is off:

- Backlog says the flow is OFF behind `SELF_SERVICE_ARCHIVE_ENABLED`; to launch, set the flag, add nav CTA, and schedule WORKSPACE-006 so the new owner can triage their own archive (`docs/BACKLOG.md:29`).
- Session 167 says PRD-060 shipped feature-flagged off (`ROADMAP.md:177`). Session 168 says flipping the flag is a user decision because it exposes a write surface to logged-in users (`docs/session_context/session-168-path-forward.md:27-28`).
- `rg -n "SELF_SERVICE_ARCHIVE_ENABLED" .env* Dockerfile app docs tests scripts` found code/tests/docs but no repo runtime config turning it on. The code default is false (`app/onboarding_routes.py:49-53`).

Missing before safely turning it on:

- Per-community owner permissions: archive creator must be able to review pending uploads, edit archive settings, and manage contributors without becoming global admin.
- Privacy enforcement: private/unlisted/public must be honored by root discovery, middleware, photo/person/help pages, sitemaps, and OG/canonical URLs.
- Upload approval scoped to owner archive: pending uploads must carry the correct `community_id`, admin screens must filter by `community_id`, and background processing must write to archive-specific paths.
- Abuse controls: CAPTCHA or equivalent for anonymous/high-risk writes, persistent rate limits, content moderation/quarantine, and clear retention/deletion rules.
- Onboarding friction decision: signup currently validates an invite code (`app/auth_routes.py:304-321`). That may be fine for a concierge Rhodesli pilot, but it is not organic self-service.

## 3. Trust & Anti-Spam Surface

Verdict: the public compare tool is the current highest-risk growth blocker.

Evidence:

- `/tools/compare` is public (`app/compare_routes.py:49-71`) and has share-preview metadata (`app/compare_routes.py:698-703`).
- `/api/compare/upload` says it uses the same upload pipeline and that photos persist to archive storage, identities, embeddings, and R2; "Compare" is a lens, not separate storage (`app/compare_routes.py:1571-1583`).
- The route rate-limits by client IP with the in-memory limiter (`app/compare_routes.py:1584-1587`, `app/rate_limit.py:1-17`). That is per-process memory, not durable or distributed protection.
- Anonymous uploads are queued as pending entries with `source="Compare Upload"` and R2 pending objects (`app/compare_routes.py:1664-1700`). The owner-provided live signal says this has produced ~51 random anonymous pending entries.
- Logged-in compare uploads are auto-approved and background-ingested (`app/compare_routes.py:1681-1726`). That becomes risky if self-service signup is widened.
- Compare upload-multiple is also public/rate-limited and can save photos for offline analysis (`app/compare_routes.py:3024-3132`). Pair upload is public/rate-limited too (`app/compare_routes.py:4207-4239`).
- A separate explicit contribution route exists and requires login (`app/compare_routes.py:3355-3408`). That suggests the product has the right concept, but `/api/compare/upload` still conflates ordinary compare use with durable pending contribution.
- Tests list public write routes as intentional and only advisory-protect compare upload with size/rate checks (`tests/test_community_routing_safety.py:252-283`, `tests/test_community_routing_safety.py:384-407`). The test comment says compare writes temp files only, which is stale against current persistent pending/R2 behavior.
- Pending upload state is still local JSON helpers in `app/main.py` (`app/main.py:2106-2127`), and startup cleanup only expires orphaned entries with missing staging dirs (`app/main.py:1290-1345`). There is no evident retention policy for valid-but-spam pending uploads.

What must exist before public invitation:

- Default compare uploads must be ephemeral. A compare query should not create a real pending archive item unless the user explicitly clicks "Contribute this to the archive."
- Anonymous durable contribution needs stronger proof-of-human and throttling: Turnstile/CAPTCHA or login, persistent IP/user/fingerprint limits, upload volume caps, and global kill switch.
- Moderation must be community-scoped, bulk-manageable, and able to quarantine/delete R2 objects and pending metadata cleanly.
- Content-liability policy must be visible in-product: permitted content, consent expectations, takedown process, and retention window for anonymous uploads.
- Logged-in does not equal trusted. Auto-approving compare uploads for any logged-in user is incompatible with broad self-service signup.

## 4. UX Growth Loop

Target loop: find -> share -> recognize -> contribute -> notify -> more finds.

What is strong:

- Session 165 shipped shareable person-photo galleries and person-scoped photo navigation (`ROADMAP.md:179`). Code has public person pages and a dedicated person gallery route (`app/person_routes.py:1892-1964`).
- Session 168 shipped growth-loop/share-preview work: community-scoped `/help`, community-aware copy, OG tags, mobile tap targets, tool `og:image`, conditional person `og:image`, search, robots/sitemap (`ROADMAP.md:175`).
- Photo pages have OG title/description/image/url metadata (`app/page_routes.py:12093-12155`), share buttons (`app/page_routes.py:12666-12680`), identify mode for non-admins (`app/page_routes.py:12710-12722`), and Help Identify CTAs (`app/page_routes.py:13039-13100`).
- Help Identify creates annotation submissions and fires `help_identify_submitted` PostHog events (`app/page_routes.py:5491-5587`). PostHog plumbing exists (`app/main.py:236-248`).

Weakest links:

- Contribution status/retention is weak. Prior eval already said visitors can submit but do not get visible status or notify-on-review (`docs/fable-eval/SITE_VISION_AUDIT.md:38-46`). GROWTH_10X made this Bet 2, with session tracking and notification as the unlock (`docs/fable-eval/GROWTH_10X.md:44-68`).
- Compare is a confusing front door. It invites a high-intent user to upload a face, then silently turns anonymous compare inputs into moderation work. That undermines trust for families and creates operational load.
- Canonical/share measurement is not complete. Session 168 deferred canonical URL fixes and shared-person badge (`docs/session_context/session-168-path-forward.md:7-20`). Backlog still says `/c/<slug>` pages emit canonical URLs without the community prefix (`docs/BACKLOG.md:99-103`) and public shared-person badges remain open (`docs/BACKLOG.md:104-107`).
- Growth-loop analytics are partial. There are events for uploads, compare requests, and identify submissions (`app/upload_routes.py:797-805`, `app/compare_routes.py:1657-1662`, `app/page_routes.py:5584-5587`), but prior GROWTH_10X acceptance still calls for share-click, page-view-from-share, and identify-submit funnel measurement (`docs/fable-eval/GROWTH_10X.md:26-42`).
- Mobile is improved but not proven. Session 168 shipped 44px tap targets (`ROADMAP.md:175`), but the next-session path still calls for mobile audit continuation (`docs/session_context/session-168-path-forward.md:7-20`).

Prior run missed or underweighted:

- The compare abuse surface is not adjacent to growth; it is on the exact public front door a new community would use.
- Self-service being "built but off" is less important than the owner-permission gap after it is turned on.
- Privacy/discovery enforcement is now a first-order issue because archives can be created with owner/privacy fields.
- The docs still overstate or misdescribe the architecture in places; Fable should rely on code and roadmap lines, not just architecture docs.

## 5. Top 10 Work Items

Ranked to reach "safe to invite other Rhodeslis."

| Rank | Title | Why it blocks growth | Size | Acceptance criterion |
|---:|---|---|---|---|
| 1 | Split compare query from archive contribution | Current public compare uploads create durable pending work and R2 objects; this is the source of the 51 spam entries. | M | Anonymous `/api/compare/upload` produces only ephemeral compare results; a pending upload is created only after an explicit "Contribute" action. |
| 2 | Add durable abuse controls to public upload surfaces | In-memory rate limits are not enough for a public front door; no CAPTCHA exists in app code. | M | Anonymous file-write routes require Turnstile/CAPTCHA or login, use persistent rate limits, enforce global daily caps, and expose a kill switch. |
| 3 | Quarantine and bulk-manage compare spam | Admin trust collapses if every outreach creates a manual spam queue. | S | Admin can filter `source=Compare Upload`, bulk reject/delete entries, and remove associated staging/R2 objects; existing spam is cleared or quarantined. |
| 4 | Implement per-community owner permissions | A second archive owner cannot triage or manage their own archive without global admin. | L | Archive owner can approve/reject uploads, edit archive settings, and invite collaborators only within their community; cannot access other archives' admin surfaces. |
| 5 | Enforce community privacy states | `privacy=unlisted/private` is stored but not visibly enforced at routing/root discovery. | M | Private archives require authorization, unlisted archives are excluded from root/sitemap/search, and all community pages share one access check. |
| 6 | Make upload moderation archive-scoped end-to-end | Pending metadata uses `community_id` but admin filters use `community`; compare pending lacks scoped ownership. | M | Every pending item has `community_id`, all moderation lists filter on it, approvals attach photos/identities to that community, and tests cover two unrelated communities. |
| 7 | Scope storage paths by archive | PRD-060 calls for per-archive R2 prefixes, but raw uploads use generic `raw_photos/{filename}`. | M | New uploads for non-default communities land under an archive/community prefix and approved photo URLs resolve without cross-archive path assumptions. |
| 8 | Add visible contribution status and notification | The recognize -> contribute loop does not compound if helpers never know what happened. | M | Anonymous/session-based and logged-in contributors can see pending/approved/rejected status and optionally receive review notifications. |
| 9 | Finish share loop measurement and canonical fixes | Growth cannot be tuned without knowing whether shares create recognition/contribution. | S | Community-prefixed canonical URLs match `og:url`; PostHog captures share-click, share-origin page view, identify submit, and contribution completion. |
| 10 | Launch a guided Rhodesli pilot onboarding path | Broad self-service is premature, but invite-only onboarding can create learning data. | M | A known family can receive a link, create or receive an archive, upload photos, invite relatives to help identify, and complete the loop without site-owner data edits. |

## 6. Three Concrete Growth Bets

### Bet 1: Safe Compare-to-Contribution Funnel

Hypothesis: face compare can be the highest-converting public hook if compare is ephemeral by default and contribution is explicit.

Plan: keep `/tools/compare` public, require a deliberate "Contribute to this archive" step, add CAPTCHA/login for durable submission, and instrument compare -> contribute -> approved.

Why it compounds: every safe contribution adds faces/photos that improve future recognition and share targets.

Kill criterion: after 30 days or 500 compare sessions, fewer than 5% start contribution or more than 10% of durable submissions are spam/rejected for abuse.

### Bet 2: Concierge Multi-Archive Pilot

Hypothesis: 2-3 Rhodes-descended families can validate the multi-community workflow before broad self-service.

Plan: keep `SELF_SERVICE_ARCHIVE_ENABLED` off publicly, create/allowlist pilot archives, give owners scoped moderation, and run a complete upload -> share -> identify -> approve cycle.

Why it compounds: each pilot creates reusable onboarding copy, permission requirements, and cross-family identity-link cases.

Kill criterion: within 45 days, fewer than two pilot archives reach 50 photos or fewer than one non-owner relative contributes an identification/memory per archive.

### Bet 3: Shareable Person Pages as the Viral Unit

Hypothesis: a person page or person-photo gallery is a better share object than a whole archive because relatives recognize names/faces faster.

Plan: finish canonical fixes, add share-origin analytics, add the public shared-person/community badge where privacy permits, and make "Do you recognize this person?" the default CTA on shared person pages.

Why it compounds: each recognized person improves navigation, search, and the probability that another relative finds a known face.

Kill criterion: after 30 days of instrumented shares, fewer than 10 share-originated sessions or fewer than two identify submissions come from person-page shares.

## Final Recommendation

Do not announce broad self-service yet. First, fix the compare/contribution boundary and owner-scoped moderation. Then run an invite-only Rhodesli pilot using real families and measure whether shares lead to identifications. The product has enough of the growth loop to learn, but not enough trust boundary to absorb anonymous traffic safely.
