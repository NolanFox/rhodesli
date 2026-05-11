# Facebook DOM Parser Strategy — Session 159 Research Brief

**Scope**: Extracting post content (text, author, date, images, comments, tags) from a manually-captured Facebook group post DOM dump.

**Constraints**: No live scraping. User pre-opens the post in Chrome (logged in), expands comments manually. Claude reads DOM via Chrome MCP `read_page`. Parser must be DEFENSIVE — Facebook's obfuscated class names (e.g. `x1n2onr6 x1ja2u2z`, `xt0b8zv x1jx94hy`) change without warning.

**Bottom line up front**: Build the parser around **aria-label patterns**, **role attributes**, and a small set of **structural anchors** (e.g. "first `<h3>` inside `[role=article]`"). Treat obfuscated classes as the LAST fallback, not the first signal. Save raw HTML alongside parsed JSON every time, so the parser can be re-run when patterns shift.

---

## 1. Post Wrapper — `[role="article"]`

**The single most stable anchor on Facebook is `role="article"`.** This wraps every individual post and every individual top-level comment. It has been stable across multiple Facebook redesigns because it's mandated by accessibility tooling (screen readers depend on it).

Recommended top-level selector:

```python
post_wrapper = soup.select_one('div[role="article"]')   # first article on the page = the post
all_articles = soup.select('div[role="article"]')        # includes post + every comment article
```

**Distinguishing the post from its comments**: The post `[role="article"]` typically has `aria-label=""` (empty/null) or carries the post-author label, while comment articles have `aria-label="Comment by <Name>"` or `aria-label="Reply by <Name>"`. Filter:

```python
def is_post(article):
    label = (article.get("aria-label") or "").lower()
    return not label.startswith(("comment by", "reply by", "antwoord van", "opmerking van"))
```

(Note: Facebook localizes aria-labels by user locale — English `Comment by` / `Reply by`, Dutch `Opmerking` / `Antwoord van`, etc. We assume English UI per project standard; record locale at capture time.)

**Source**: [Web Scraping with ARIA attributes](https://dev.to/mcreel/web-scraping-use-aria-attributes-to-crawl-accessible-components-3lof), [FB Comments Exporter Userscript](https://github.com/disrex-group/FB-Comments-Exporter-User-script) (5 detection methods including aria-label pattern matching).

---

## 2. Post Author Name

Inside the post `[role="article"]`, the author name is rendered as the **first `<h2>` or `<h3>`** containing a link to the author's profile. Modern FB (2024-2026) uses `<h2>` for the post author in feed view, `<h3>` in some embedded contexts.

```python
def extract_post_author(post_article):
    # Try h2 first, fall back to h3, fall back to first strong-link
    for tag in ("h2", "h3", "h4"):
        heading = post_article.find(tag)
        if heading:
            link = heading.find("a", href=True)
            if link:
                return {
                    "name": link.get_text(strip=True),
                    "profile_url": link["href"],   # normalize below
                    "selector_used": tag,
                }
    # Fallback: first <strong> with a profile link
    strong = post_article.find("strong")
    if strong and strong.find("a"):
        return {...}
    return None
```

**Profile URL normalization** — Facebook serves two forms:
- `/profile.php?id=100012345678901` — numeric ID format
- `/firstname.lastname` or `/firstname.lastname.NNN` — vanity URL

Strip query params except `id=` for `profile.php` URLs. Record both raw and normalized.

---

## 3. Post Date

The date in modern Facebook is a **link wrapping a `<span>` of relative time text** (e.g. "5h", "Yesterday at 3:14 PM", "March 5"). Two stable signals:

1. **Hover tooltip via `aria-label`** — when present, the anchor or its child has `aria-label="Sunday, March 5, 2026 at 3:14 PM"` (full absolute timestamp).
2. **`<abbr>` element** — older FB markup used `<abbr title="Sunday, March 5, 2026 at 3:14 PM">5h</abbr>`. Less common in current Comet UI but still appears in some fallback paths.

```python
def extract_post_date(post_article):
    # Method 1: aria-label on any link inside the post header
    for a in post_article.find_all("a"):
        aria = a.get("aria-label", "")
        if aria and any(c.isdigit() for c in aria) and any(m in aria.lower()
            for m in ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec",
                     "monday","tuesday","wednesday","thursday","friday","saturday","sunday",
                     "yesterday","hour","minute","at "]):
            return {"absolute": aria, "relative": a.get_text(strip=True), "url": a.get("href")}
    # Method 2: <abbr title=...>
    abbr = post_article.find("abbr")
    if abbr and abbr.get("title"):
        return {"absolute": abbr["title"], "relative": abbr.get_text(strip=True)}
    # Method 3: parse permalink URL for post ID + reconstruct
    # FB permalinks: /groups/{slug}/permalink/{post_id}/ or /groups/{slug}/posts/{post_id}/
    return None
```

**Caveat**: The permalink URL is more reliable than the timestamp text for ID tracking. Always record the permalink href even if the date string is ambiguous. Per [Apify docs](https://apify.com/scrapier/facebook-group-post-scraper) and StackOverflow consensus.

---

## 4. Post Body Text

Historically the most-cited selector is `div[data-ad-preview="message"]` ([Sabry 2025](https://medium.com/@AbdelRhman_Sabry/scraping-facebook-in-2025-combining-selenium-and-beautifulsoup-for-effective-data-extraction-95bc8d705889)). This attribute is **less stable than `role="article"`** but more stable than obfuscated classes. Use as primary, with fallback to "largest text block in the article that isn't header/footer."

```python
def extract_post_body(post_article):
    # Primary: data-ad-preview="message"
    body = post_article.select_one('div[data-ad-preview="message"]')
    if body:
        return _flatten_text(body)
    # Fallback: data-ad-comet-preview="message" (newer Comet variant)
    body = post_article.select_one('div[data-ad-comet-preview="message"]')
    if body:
        return _flatten_text(body)
    # Fallback: dir="auto" + longest text region not inside a comment article
    candidates = [d for d in post_article.find_all("div", dir="auto")
                  if not d.find_parent('div[role="article"][aria-label]')]
    if candidates:
        return _flatten_text(max(candidates, key=lambda d: len(d.get_text())))
    return None
```

**"See more" / "See less" handling**: When a post body is truncated, FB renders a button with text content "See more" (locale-dependent). The full text is usually NOT in the DOM until the button is clicked. **The user MUST expand "See more" manually before DOM capture**, OR Claude must click it via Chrome MCP. Detect by:

```python
see_more = post_article.find("div", string=lambda s: s and s.strip() in ("See more", "See More"))
# or buttons with role="button"
see_more = post_article.find(attrs={"role": "button"}, string=lambda s: s and "See more" in s)
```

The script should WARN if a "See more" button is present in the captured DOM — that means the post body is truncated.

---

## 5. Image URLs

### 5.1 Where images live

Post images appear as `<img>` tags inside the post `[role="article"]`. They have `src` (and sometimes `srcset`) pointing to `*.fbcdn.net`. Multiple-image posts use a grid of `<img>` tags, sometimes lazy-loaded.

### 5.2 Signed URL expiration

Per [kevinzg/facebook-scraper issue #213](https://github.com/kevinzg/facebook-scraper/issues/213) and [LinkedIn post on FB image expiry](https://www.linkedin.com/pulse/did-you-know-facebook-image-links-may-expire-lothar):

- fbcdn URLs contain query params: `oh=<hash>` (signature) and `oe=<hex_expiration_timestamp>`
- `oe` is a hex-encoded Unix timestamp — typical TTL is **~30 days**, sometimes shorter
- The URL is signed for the specific viewer's session in some cases (avatar URLs, especially)
- **Mandatory**: download every image to local R2/disk at capture time. Do not store fbcdn URLs as canonical.

### 5.3 Distinguishing post images from avatars / reaction icons / comment images

**Heuristics, in priority order:**

1. **Parent article check** — image must be inside the POST `[role="article"]` but NOT inside a CHILD `[role="article"]` (which would make it a comment image).
   ```python
   def is_in_post_only(img, post_article):
       comment_parent = img.find_parent('div[role="article"][aria-label]')
       return img in post_article.descendants and comment_parent is None
   ```
2. **Size threshold** — avatars are typically ≤ 60×60 (CSS `width`/`height` or `style` attribute). Post images are typically ≥ 200px on the long axis. Reaction icons are ≤ 24×24.
3. **URL path hints**:
   - Avatar/profile: path contains `p<NNN>x<NNN>` (e.g. `p60x60`, `p100x100`) or `s50x50`
   - Reactions (👍 ❤️ etc.): usually SVG inline or short path like `t39.2365-6` (emoji sprite)
   - Post images: path contains `t39.30808-6` or `t31.18172-8` for full-res variants
4. **`role` / `aria-label`** — `<img alt="May be an image of ...">` is FB's AI-generated alt-text for post photos. Avatars typically have `alt="<Name>"`. This is a strong signal: alt text starting with "May be an image of" = post photo (high confidence).

```python
def classify_image(img, post_article):
    alt = (img.get("alt") or "")
    src = img.get("src", "")
    if alt.lower().startswith("may be an image"):
        return "post_image"
    if "p60x60" in src or "p100x100" in src or "p50x50" in src:
        return "avatar"
    if int(img.get("width") or 0) > 200 or int(img.get("height") or 0) > 200:
        return "post_image"
    return "unknown"
```

### 5.4 Size variants

fbcdn serves multiple sizes via different URL paths. The DOM typically renders a medium variant in `src` and includes a `srcset` with multiple densities. To get the highest-resolution version:

- Parse `srcset` and take the largest descriptor (`2x` or highest width).
- Some posts also have a `<a href="...">` wrapping the `<img>` linking to a full-size view; check the anchor href.
- Best practice: **always download whatever variant is in `src`**, and ALSO record `srcset` raw value for future re-fetch.

---

## 6. Comment Thread Structure

### 6.1 Top-level vs nested

Each comment is its own `<div role="article">` with `aria-label="Comment by <Name>"`. Replies (nested) have `aria-label="Reply by <Name>"`. The depth is determined by **DOM hierarchy** — replies live inside a sibling/descendant container of their parent comment, not as siblings of the top-level comment list.

The cleanest extraction is to walk all `[role="article"]` elements in document order and use the **CSS indentation** or **parent-article chain** to determine depth:

```python
def comment_depth(comment_article, post_article):
    """Count how many ancestor [role=article][aria-label] are between this comment and the post."""
    depth = 0
    parent = comment_article.parent
    while parent and parent != post_article:
        if (parent.name == "div" and parent.get("role") == "article"
            and parent.get("aria-label")):
            depth += 1
        parent = parent.parent
    return depth   # 0 = top-level comment, 1+ = nested reply
```

### 6.2 Comment author + text

Inside each comment article:
- **Author**: first `<a>` with `role="link"` near the top of the article, typically inside a `<span>` with text styling. Or look for `<a>` whose `href` matches a profile pattern (`/profile.php?id=` or `/{vanity}`).
- **Text**: `<div dir="auto">` containing the comment body. Skip nodes that contain ONLY a link (those are mentions in author names).

```python
def extract_comment(comment_article):
    label = comment_article.get("aria-label", "")
    # aria-label format: "Comment by Jane Doe 2 hours ago" or "Reply by Jane Doe ..."
    # The author name follows "by " and precedes a time phrase
    author_name = _parse_aria_label_author(label)
    # Text body: longest dir="auto" div not containing another article
    text_divs = [d for d in comment_article.find_all("div", dir="auto")
                 if not d.find('div[role="article"]')]
    text = _flatten_text(max(text_divs, key=lambda d: len(d.get_text()))) if text_divs else ""
    # Timestamp: <a> with aria-label containing date, OR <abbr title="...">
    ts = _extract_timestamp(comment_article)
    return {"author": author_name, "text": text, "timestamp": ts, "raw_aria_label": label}
```

### 6.3 Timestamp on comments

Same patterns as the post date — look for `<abbr title="...">` first, then `<a aria-label="...">` with date text, finally fall back to the relative-time text inside the link.

### 6.4 "View N more comments" / "View N more replies"

These are `<div role="button">` (sometimes `<span role="button">`) with text matching patterns like:
- `View N more replies`
- `View N more comments`
- `N replies`
- `View more comments`
- `View previous comments`

```python
expansion_buttons = post_article.find_all(
    attrs={"role": "button"},
    string=lambda s: s and any(p in s for p in [
        "View more", "View previous", "more repl", "more comment", "Show more"
    ])
)
```

**If any expansion buttons are present in the captured DOM, the comment thread is INCOMPLETE.** Either click them via Chrome MCP and re-capture, or record the count and mark the capture as `partial=true`.

### 6.5 Detecting complete expansion

A capture is "complete" if:
- Zero expansion buttons match the patterns in 6.4
- The total comment count (extracted from the post's "X comments" reaction bar) equals the count of `[role="article"][aria-label*="Comment by"]` + `[role="article"][aria-label*="Reply by"]` in the DOM

If the counts disagree, log a warning and mark `complete=false`.

---

## 7. Tagged People

### 7.1 In post body

Mentions/tags in the post text are rendered as `<a>` tags inside the post body (`data-ad-preview="message"` container) with `href` matching either `/profile.php?id=...` or `/{vanity}` and the link text being the tagged person's display name.

```python
def extract_tags_from_body(body_div):
    tags = []
    for a in body_div.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/profile.php?id=") or _is_vanity_url(href):
            tags.append({
                "name": a.get_text(strip=True),
                "profile_url": href,
                "context": "post_body",
            })
    return tags
```

### 7.2 In comments

Same pattern, applied per comment article — any `<a>` linking to a profile from inside the comment text body is a mention.

### 7.3 @mention vs auto-tag

- **@mention** in body text: inline `<a>` inside the message text.
- **Photo auto-tag** ("Jane was with John Doe"): appears as a separate line ABOVE the post body, often inside a `<span>` with a child `<a>`. Pattern: text contains "was with" or "is with" (locale-dependent).
- **Tagged in photo metadata**: only visible on the photo's own page, not in feed view. Out of scope for this parser.

The script should extract `@mention` (in-body) and `with-tags` (auto) separately but combine into a single `tagged_people` list with `mention_type` field.

---

## 8. Stable Selector Strategy — Priority Order

When writing each extractor, try selectors in this order. **Stop at the first one that returns a non-empty result.**

| Priority | Signal | Stability | Notes |
|----------|--------|-----------|-------|
| 1 | `role="article"` | VERY HIGH | Mandated by accessibility tooling; stable across years |
| 2 | `aria-label` text patterns (`"Comment by"`, `"Reply by"`, dates) | HIGH | Localized — record locale at capture |
| 3 | `role="button"` + text content match | HIGH | Generic role + specific text |
| 4 | `data-ad-preview="message"` / `data-ad-comet-preview="message"` | MEDIUM | Stable for years but FB could rename |
| 5 | `<h2>` / `<h3>` / `<abbr>` / `<img alt="May be an image of...">` semantic tags | MEDIUM | Semantic HTML; stable but FB sometimes wraps in extra divs |
| 6 | `href` patterns (`/profile.php?id=`, `/groups/`, etc.) | MEDIUM-HIGH | URL schemas change rarely |
| 7 | Structural ("first `<h2>` inside `[role=article]`") | MEDIUM | Robust if anchored on role/aria |
| 8 | Obfuscated CSS classes (e.g. `x1n2onr6 x1ja2u2z`) | LOW — DO NOT USE except as last-resort emergency fallback | These rotate; assume any given class will break within 3-6 months |

**Rule**: Never write a selector that depends SOLELY on obfuscated classes. Always pair them with a role/aria anchor.

---

## 9. Comment Expansion via Chrome MCP

The session prompt states: user opens post in Chrome, expands MOST comments manually. Claude needs to handle the remainder.

### Recommended flow

1. **User opens** the FB post URL in Chrome and expands as much as they can manually (faster + their session is logged in).
2. **User runs the Python script** which:
   a. Calls `mcp__claude-in-chrome__read_page` to get the current DOM.
   b. Searches for any `role="button"` with text matching the expansion patterns from §6.4.
   c. For each remaining expansion button, calls `mcp__claude-in-chrome__find` to locate it, then `mcp__claude-in-chrome__left_click` to click. Wait ~500ms between clicks (FB lazy-loads, can rate-limit).
   d. After each batch of clicks, re-call `read_page` and re-scan for buttons. Loop until zero expansion buttons remain OR a max iteration count (e.g. 20) is hit.
   e. Final `read_page` → save the raw HTML to disk with timestamp + URL.
   f. Run BeautifulSoup parser against the saved HTML.

### Why this is OK under the project's READ-ONLY production rule

The browser-read-only rule (`.claude/rules/browser-read-only.md`) forbids clicking on rhodesli.nolanandrewfox.com production. Clicking "View more replies" on facebook.com is a **read-expansion action on a third-party site to surface already-public content** — it does not modify any data the project owns. This should be documented in the session prompt as an explicit, narrow exception.

### Tools to load (ToolSearch at session start)

`read_page` (DOM capture) · `find` (locate buttons) · `left_click` (READ-EXPANSION only) · `tabs_context_mcp` (confirm URL pre-click) · `get_page_text` (dialog sanity check).

---

## 10. Parser Architecture

### 10.1 Module layout

```
scripts/fb_post_extractor/
    capture.py     # Chrome MCP: expand comments, save raw HTML
    parse.py       # BeautifulSoup parser (extractors per §1-7)
    classify.py    # Image classifier (avatar / post / reaction)
    schema.py      # Pydantic output models
    fixtures/      # synthetic_*.html (see §11)
    tests/         # unit + integration tests
```

### 10.2 Defensive first-pass extraction

Best-effort, never raise. Each field carries a confidence:

| Field | Confidence source |
|-------|-------------------|
| `post.author.{name,profile_url}` | h2+link (high) → fallback chain (medium) |
| `post.body_text` | `data-ad-preview="message"` (high) → longest `dir="auto"` (medium) |
| `post.timestamp_absolute` | `aria-label` / `abbr@title` (high) → relative-only (low) |
| `post.timestamp_relative` | always |
| `post.permalink` | URL itself (high) |
| `post.images[]` | URLs always saved; classification per-image is heuristic |
| `post.tagged_people[]` | medium — best-effort link extraction |
| `comments[]` | per-comment confidence flag |
| `comments[].depth` | structural traversal (high) |
| `comments[].author.name` | aria-label (high) |
| `comments[].text` | `dir="auto"` (high) → fallback (medium) |
| `meta.{complete, locale_guess, parser_version, captured_at, captured_url}` | always set |

### 10.3 What to defer to admin approval queue

- Cross-reference of `tagged_people` to existing identities in the archive (auto-matching by name is unsafe — Lesson 171 / Fader)
- Photo download + face detection (separate pipeline, AD-110 serving-path contract)
- Comment-author identity resolution
- Date parsing into structured year/month/day (the absolute timestamp is captured as a string; structured parsing can happen in a separate enrichment pass)

### 10.4 Raw HTML preservation

**Every capture saves three artifacts atomically**:
```
data/fb_captures/
    {capture_id}/
        raw.html              # full DOM as returned by read_page
        parsed.json           # structured extraction
        meta.json             # parser_version, captured_at, source_url, completeness flags
```

Re-parse path: if a future parser_version improves extraction, re-run against `raw.html` — never re-fetch from facebook.com. This is the project's standard pattern (matches AD-228 ml_runs provenance approach).

### 10.5 `parser_version` field

Semantic versioning:
- `MAJOR` bumps when output schema changes (downstream consumers must update).
- `MINOR` bumps when new fields added (backward compatible).
- `PATCH` bumps on selector changes that don't affect schema.

Initial release: `0.1.0`. The version is persisted in every `parsed.json` AND in every `meta.json`. Re-parse jobs record both `original_parser_version` and `reparsed_with_version`.

### 10.6 Testing strategy

- Unit tests against synthetic fixtures (see §11). NEVER commit real FB HTML.
- Each extractor: happy-path + missing-field + selector-changed (remove primary selector, confirm fallback) tests.
- Integration: parse synthetic fixtures end-to-end, assert against golden JSON.
- Property: feed empty `<html></html>` → no exceptions, all fields default to None/[].

---

## 11. Synthetic Fixture Sketch

The synthetic HTML must be **unmistakably synthetic** so we never confuse it with a real FB capture, AND must exercise every selector we depend on. Do NOT copy real FB HTML — author it from scratch.

### Minimal fixture sketch (`fixtures/synthetic_minimal.html`)

```html
<!DOCTYPE html><html lang="en">
<head><title>SYNTHETIC FIXTURE - NOT REAL FACEBOOK</title></head>
<body>
  <div role="article" aria-label="" data-fixture-id="post-1">
    <h2><a href="/profile.php?id=999999999999999" role="link">SYNTHETIC Jane Doe</a></h2>
    <a href="/groups/synthetic-group/permalink/8888888888888888/"
       aria-label="Sunday, March 5, 2026 at 3:14 PM"><span>5h</span></a>
    <div data-ad-preview="message">
      <div dir="auto">SYNTHETIC post body mentioning
        <a href="/profile.php?id=111111111111111">SYNTHETIC John Smith</a>.</div>
    </div>
    <img src="https://scontent.synthetic.example/v/t39.30808-6/syn.jpg?oh=fake&oe=68000000"
         alt="May be an image of SYNTHETIC scene" width="800" height="600" />
    <img src="https://scontent.synthetic.example/v/p60x60/syn_avatar.jpg"
         alt="SYNTHETIC Jane Doe" width="60" height="60" />
    <div role="article" aria-label="Comment by SYNTHETIC Bob 2 hours ago">
      <a href="/profile.php?id=222222222222222">SYNTHETIC Bob Wilson</a>
      <div dir="auto">SYNTHETIC comment text.</div>
      <abbr title="Sunday, March 5, 2026 at 1:14 PM">2h</abbr>
      <div role="article" aria-label="Reply by SYNTHETIC Alice 1 hour ago">
        <a href="/synthetic.alice">SYNTHETIC Alice Chen</a>
        <div dir="auto">SYNTHETIC reply mentioning
          <a href="/profile.php?id=222222222222222">SYNTHETIC Bob Wilson</a>.</div>
        <abbr title="Sunday, March 5, 2026 at 2:14 PM">1h</abbr>
      </div>
    </div>
    <div role="button">View 3 more replies</div>
  </div>
</body></html>
```

### Variants to author

- `synthetic_complete.html` — no expansion buttons (asserts `meta.complete=true`).
- `synthetic_truncated.html` — has "See more" in post body (asserts warning emitted).
- `synthetic_multi_image.html` — 4 post images + 2 avatars + 1 reaction icon.
- `synthetic_locale_dutch.html` — `aria-label="Opmerking van ..."` (asserts locale fallback).

**Marker rule**: Every fixture has `<title>SYNTHETIC FIXTURE - NOT REAL FACEBOOK</title>` and every text node is prefixed `SYNTHETIC`. A pre-commit hook should reject any HTML file in `fixtures/` lacking the marker.

---

## 12. Known Risks + Caveats

1. **DOM volatility (HIGH)** — Even role/aria-label is not immune. Plan for the parser to break ~once per quarter. Raw-HTML preservation makes recovery a re-parse job, not a re-scrape job.
2. **fbcdn URL expiration (MEDIUM-HIGH)** — Download images at capture time. ~30 day TTL. Never trust fbcdn URLs as long-term references.
3. **Localization (MEDIUM)** — aria-label patterns are locale-dependent. Record locale at capture; build per-locale pattern dicts.
4. **"See more" truncation (MEDIUM)** — If a long post body is truncated, the full text isn't in the DOM until clicked. Always check.
5. **Lazy-loaded comments (MEDIUM)** — Automated expansion loop must scroll between `read_page` calls.
6. **Rate limiting (LOW)** — User-logged-in single-post expansion is minimal surface. Keep clicks ≤ 20 per session.
7. **TOS posture** — Single-post + user-initiated + member-of-group, NOT bulk. Do not extend to crawl multiple posts automatically.
8. **AD-228 alignment** — Every capture artifact gets `ml_runs`-style provenance: `parser_version`, `chrome_mcp_version`, `captured_by_user`, target `community_id`.
9. **Lesson 171** — Auto-matching tagged people by name is unsafe; matching is a separate admin-approval phase.
10. **Lesson 162** — Parsed posts must write to Supabase admin-review queue, not a local JSON file the app doesn't read.

---

## 13. Sources

- [Sabry, A. (2025) — Scraping Facebook in 2025: Combining Selenium and BeautifulSoup](https://medium.com/@AbdelRhman_Sabry/scraping-facebook-in-2025-combining-selenium-and-beautifulsoup-for-effective-data-extraction-95bc8d705889) — `data-ad-preview="message"` selector for post body; `div[class="x1n2onr6 x1ja2u2z"]` post container (UNSTABLE — use as illustration only)
- [disrex-group/FB-Comments-Exporter-User-script (GitHub)](https://github.com/disrex-group/FB-Comments-Exporter-User-script) — 5-method detection strategy for nested comments; English + Dutch aria-label patterns
- [kevinzg/facebook-scraper issue #213 (GitHub)](https://github.com/kevinzg/facebook-scraper/issues/213) — fbcdn URL expiration, `oe` hex timestamp parameter
- [Lothar — Facebook image URLs may expire (LinkedIn)](https://www.linkedin.com/pulse/did-you-know-facebook-image-links-may-expire-lothar) — ~30 day TTL on fbcdn signed URLs
- [Web Scraping with ARIA attributes (dev.to)](https://dev.to/mcreel/web-scraping-use-aria-attributes-to-crawl-accessible-components-3lof) — general ARIA-based crawl strategy; `aria-controls`/`aria-owns` for relationships
- [CSS attribute selectors for web scraping (axiom.ai)](https://axiom.ai/blog/css-attribute-selectors) — `[aria-label*="..."]` partial-match pattern
- [Apify Facebook Group Post Scraper](https://apify.com/scrapier/facebook-group-post-scraper) — permalink URL format `/groups/{slug}/permalink/{post_id}/?comment_id=...`
- [Khalil, A. (2026) — Complete Guide to Facebook Scraper](https://medium.com/@70142078/the-complete-guide-to-facebook-scraper-how-to-scrape-facebook-posts-pages-groups-public-data-695734b89710) — `data-testid` patterns (where available) more stable than obfuscated classes
- [MDN — aria-expanded attribute](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Attributes/aria-expanded) — `aria-expanded` toggle semantics (background for "See more" detection)
- [WebScraping.AI — Nested HTML with BeautifulSoup](https://webscraping.ai/faq/beautiful-soup/how-do-i-handle-nested-html-structures-when-scraping-with-beautiful-soup) — recursive parent-chain traversal for nested depth

---

**End of brief. ~480 lines.**
