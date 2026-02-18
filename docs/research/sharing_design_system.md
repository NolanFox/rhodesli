# Sharing Design System Research

**Date:** 2026-02-17

## Growth Loop Theory

```
Find interesting thing → Share → Preview drives click →
Visitor recognizes someone → Submits response (no login) →
Explores archive → Uploads photos → Cycle repeats
```

Every page that could prompt someone to contribute knowledge
MUST be shareable with one click.

## Web Share API Pattern (Best Practice)

Three-layer approach:
1. **Web Share API** (`navigator.share`) — native share sheet on mobile
2. **Clipboard fallback** — "Copy link" on desktop browsers
3. **Toast confirmation** — visual feedback after action

```javascript
async function shareContent(title, text, url) {
  if (navigator.share) {
    try {
      await navigator.share({ title, text, url });
    } catch (e) {
      // User cancelled — not an error
    }
  } else {
    await navigator.clipboard.writeText(url);
    showToast('Link copied!');
  }
}
```

### Mobile vs Desktop

- **Mobile:** `navigator.share()` opens native share sheet (WhatsApp, iMessage, etc.)
- **Desktop:** Copy to clipboard + toast. Direct social links optional.
- Detection: `/iPhone|iPad|iPod|Android/i.test(navigator.userAgent)`

## OG Tags Standard

Every shareable page MUST have these tags:
```html
<meta property="og:title" content="[Compelling title]" />
<meta property="og:description" content="[Action-oriented description]" />
<meta property="og:image" content="[ABSOLUTE URL to image]" />
<meta property="og:url" content="[Canonical URL]" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="Rhodesli — Heritage Photo Archive" />
<meta name="twitter:card" content="summary_large_image" />
```

**CRITICAL:** `og:image` MUST be an absolute URL (https://...). Facebook, WhatsApp,
and iMessage will NOT fetch relative URLs. Face crops make compelling preview images.

## Sharing Placement Best Practices

1. Place share buttons at **natural completion points** (after viewing results, at bottom of profiles)
2. Use **icon + text** ("Share This Match"), not icon alone
3. **Action-oriented** copy: "Share with someone who might know" > "Share"
4. Show share count when available (social proof)
5. Mobile: native share sheet. Desktop: clipboard + toast.

## Rhodesli Shareable Pages

| Page | OG Title | OG Image | Share CTA |
|------|----------|----------|-----------|
| /photo/{id} | "Photo from [Collection]" | Photo thumbnail | "Share this photo" |
| /person/{id} | "[Name] — Rhodesli" | Face crop | "Do you know [Name]?" |
| /identify/{id} | "Who is this?" | Face crop | "Help identify this person" |
| /identify/{a}/match/{b} | "Same person?" | Composite faces | "Help us determine" |
| /compare/result/{id} | "[X]% Similar" | Composite faces | "Look at this comparison" |
| /collection/{slug} | "[Name] — Rhodesli" | Collection grid | "Explore this collection" |
| /tree | "Family Tree" | Tree screenshot | "Explore the family tree" |

## Implementation Components

### `share_button(url, title, text, style)`
Reusable component on every page:
- Web Share API on mobile
- Clipboard copy on desktop
- Toast confirmation
- Styles: "icon" (compact), "button" (icon+text), "link" (text), "prominent" (large CTA)

### `og_tags(title, description, image_url, canonical_url)`
Reusable in every page's `<head>`:
- All URLs converted to absolute
- Site name constant
- Twitter card included
