# Decisions for Nolan — Session 167 Track C (PRD-060 "Create Your Archive")

Track C shipped the **landing page + create form + create flow** for self-service
archive creation, wired to the existing `create_community()` Supabase primitive.
Everything below is a **policy / permission decision I deliberately did NOT make**.
To keep production behavior unchanged, the actual archive-creating WRITE is gated
behind a **default-OFF** feature flag (`SELF_SERVICE_ARCHIVE_ENABLED`). Nothing in
production changes until you flip it AND resolve these.

---

## D1 — Who is allowed to create an archive? (THE core decision) — BLOCKING

PRD-060 says "any signed-up user." But today's permission model
(`docs/architecture/PERMISSIONS.md`) is **binary**: anonymous browse + admin-only
for every write. Letting a non-admin write a `communities` row is a **brand-new
permission grant** — the first non-admin write path in the app.

**What I shipped (conservative default, behind the OFF flag):** logged-in users
only (`get_current_user` must return a user when auth is enabled). I did NOT use
`_check_admin` (that would make the feature pointless) and I did NOT allow
anonymous creation.

**Options:**
- **(a) Admin-only** — safest; but then it's not "self-service," it's just an
  admin convenience form. Recommend only as a soft launch.
- **(b) Any logged-in user** — matches PRD-060 intent. Requires you to accept the
  first non-admin write path. **My recommendation**, paired with D2 + D4.
- **(c) Logged-in + verified email** — (b) plus an email-verified check. Best
  abuse posture; needs a verified-email signal from Supabase auth (not currently
  surfaced on the `User` model — would need wiring).

**Recommendation:** (b) for launch, move to (c) once we see real usage. Flip
`SELF_SERVICE_ARCHIVE_ENABLED=true` only after you've chosen.

---

## D2 — Privacy default for new archives — BLOCKING-ish

PRD-060 Flow 1 specifies `privacy='unlisted'` (anyone with the link can view).
I shipped `unlisted`. Confirm this is what you want, vs `private` (owner-only
until they deliberately share). `unlisted` is friendlier for "share with family
immediately"; `private` is safer if you're worried about half-built archives
being linkable. **Recommendation:** keep `unlisted` per the PRD.

---

## D3 — Rate limit / abuse model

PRD-060 suggests **3 archives per user**. I implemented that as `MAX_ARCHIVES_PER_USER`
counting a user's owned, non-personal communities. Confirm the number, and decide
whether you also want: per-IP throttling on the POST (we have `app/rate_limit.py`),
a CAPTCHA, or admin approval before an archive goes live (moderation). I did **not**
add moderation — new archives would be immediately live (subject to D2 privacy).
**Recommendation:** keep 3/user for launch; add per-IP throttle if (b)/(c) in D1.

---

## D4 — `owner_id` → community ownership permission semantics

I write `owner_id = user.id` and `admin_emails = [user.email (+ optional contact)]`.
For the owner to actually **manage** their archive (upload, confirm faces, edit
settings), the app's write routes must treat the community owner as an admin **for
that community**. Today `_check_admin` checks a global `ADMIN_EMAILS` list, NOT
per-community ownership. **Per-community owner permissions are NOT implemented**
(that's WORKSPACE-006, still open). So a freshly created archive's owner can SEE
their archive but cannot yet triage it unless they're also a global admin.

**Decision needed:** is creating the archive row enough for this session (owner
manages later, once WORKSPACE-006 lands), or do you want owner-as-community-admin
wired now? I scoped it OUT (it's a cross-cutting permission change spanning many
routes). **Recommendation:** ship create-flow now; schedule WORKSPACE-006 next.

---

## D5 — Schema items deferred (NO migration written, per guardrails)

PRD-060 also lists, for **v1.1** (not this session):
- new `archive_invites` table (viewer/contributor/admin invite links)
- new `communities.max_photos` column (default 500)

I did **not** create either — they require a DB migration (a write to schema) and
the invite/role model is itself a permission decision. The `config` JSONB I write
(`{"created_via": "self_service", "onboarding_version": 1}`) is forward-compatible.
**Recommendation:** defer both to the WORKSPACE sharing-mode arc.

---

## D6 — First-upload entrypoint

On success the POST redirects to `/c/<slug>/` (the community dashboard), which is
the natural "upload your first photo" entrypoint (PRD-060 Flow 2 reuses the
existing `/c/<slug>/upload`). I did **not** build any new upload code. Confirm the
dashboard is the right landing spot, or if you'd rather deep-link straight to the
upload page.

---

## How to enable (once D1/D2/D3 are decided)

1. Set env `SELF_SERVICE_ARCHIVE_ENABLED=true` (Railway + local `.env`).
2. If you chose anything other than "logged-in users," adjust the auth gate in
   `app/onboarding_routes.py:post` (clearly commented).
3. Decide D4 (owner permissions) — otherwise owners see but can't triage.
4. Add a nav/CTA link to `/create-archive` (intentionally NOT added yet — it's
   invisible until you wire it, so the OFF flag + no-CTA = truly dormant).
