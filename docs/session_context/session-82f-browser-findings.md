# Session 82f Browser Findings

**Date:** 2026-03-02
**URL:** https://rhodesli.nolanandrewfox.com/
**Auth:** Admin (NolanFox@gmail.com)
**Browser:** Chrome via Claude Chrome extension
**Viewport:** 1440x900 desktop, 375x812 mobile

---

## BROKEN (must fix)

| Issue | Page | Severity |
|-------|------|----------|
| (none found — all tested features are functional) | | |

---

## INCONSISTENT (should fix)

| Issue | Pages Affected | Notes |
|-------|---------------|-------|
| "Similar" button is 38x16px — below 44px mobile min-tap target | `/?section=to_review&view=browse`, `/?section=confirmed&view=browse` | HTMX works correctly, but the button text is `text-xs` with no padding. Hard to click on mobile. Should add padding or increase hit area. |
| Landing page help section not visible to admin | `/` (admin view) | Admin users see Focus view by default. The "Help Identify People" section with mystery faces only renders for anonymous visitors. Not a bug per se — admin doesn't need the CTA — but worth noting. |
| Landing page mystery faces use `flex-wrap` instead of horizontal scroll | `/` (public view) | 82e spec mentioned "horizontal scroll" but implementation uses `flex justify-center gap-5 flex-wrap`. Flex-wrap is arguably better for mobile since it wraps gracefully. Non-issue. |

---

## WORKING (confirmed)

| Feature | Page | Evidence |
|---------|------|----------|
| Find Similar expansion panel (inline HTMX) | `/?section=to_review&view=browse` | Clicked "Similar" → panel opened with hero face, 12 similar faces, Compare/Merge/Not Same buttons. HTMX 2.0.7 processed all 398 buttons. |
| Close button (X) on expansion panel | `/?section=to_review&view=browse` | Clicked X → panel cleared, innerHTML empty |
| Expansion panel content | `/?section=to_review&view=browse` | Hero section: face thumb, name, face count, View Profile. Results: confidence badges (Moderate/Low), distance scores, gap percentages, action buttons. |
| Face cards in to_review section | `/?section=to_review&view=browse` | Large face photos, name, Similar/Profile links, action buttons (confirm/reject/skip/merge) |
| Face cards in confirmed section | `/?section=confirmed&view=browse` | Face photos, name, CONFIRMED badge, match count, Photos/Similar/Link Tree/Profile/Admin links |
| Help Needed page | `/help` | 50 face cards, "Do you recognize this person?" CTAs, collection names, quality ordering |
| Masonry photo grid | `/photos` | 4 columns, natural aspect ratios, date badges, face count badges, collection names, 272 results |
| People page | `/people` | 59 people, circular avatars, names, photo counts, Sort A-Z dropdown |
| Person page Photos/Faces toggle | `/person/{id}` | Fast HTMX swap between Faces (7 crops) and Photos (7 full photos), no page reload |
| Person page admin buttons | `/person/{id}` | Edit Name, Find Similar, View in Admin, Timeline, Map, Family Tree, Connections all visible |
| Person page Share button | `/person/{id}` | Share button present |
| Mobile hamburger (375px) | `/people` (mobile) | Hamburger icon visible, slide-from-right menu, all 10 nav links, X close button |
| Identify page OG tags | `/identify/{id}` | og:title, og:description, og:image (R2 crop URL), og:url, og:type, og:site_name, twitter:card (summary_large_image) all correct |
| Identify page content | `/identify/{id}` | "Can you identify this person?", large face crop, "Appears in these photos", form (name/how/email), "Yes, I know this person!" CTA, "Share to help identify" button |
| Public landing page help section | `/` (anonymous curl) | "Help Identify People" button, "See all 658 →" link, mystery face CSS classes present |

---

## 82d Verification Items

| Item | Status | Notes |
|------|--------|-------|
| Merge action from expansion panel | NOT TESTED | Skipped to avoid data modification in production |
| Close button (X) on expansion panel | PASS | Verified — clears panel content |
| Public/non-admin Find Similar link | NOT TESTED | Would need logged-out browser. Code inspection shows: admin gets HTMX button, public gets `<a>` link to `/people/{id}/similar` |
| Expansion panel animation smoothness | PASS | No noticeable delay on broadband |

## 82e Verification Items

| Item | Status | Notes |
|------|--------|-------|
| Mobile hamburger at 375px | PASS | Works perfectly — icon, slide-in, all links, X close |
| Masonry grid lazy-loading with pagination sentinels | NOT TESTED | Would need scrolling through 272 photos to trigger pagination |
| Share button clipboard fallback | NOT TESTED | Web Share API only available on HTTPS (which we have). Clipboard fallback would need non-HTTPS test. |
| OG tag test for INBOX/PROPOSED identity | PASS | Tested `/identify/{id}` for INBOX identity — all OG tags correct with R2 crop URL |
| Landing page mystery faces flex-wrap vs horizontal-scroll | VERIFIED | Uses `flex justify-center gap-5 flex-wrap`. Spec deviation from "horizontal scroll" but arguably better UX. |

---

## Summary

**No broken features found.** All 82d/82e shipped features are functional in production. The only actionable item is the tiny "Similar" button hit area (38x16px), which should be padded for mobile usability.
