# PRD-017: Sharing Design System

**Status:** IN PROGRESS
**Priority:** HIGH
**Session:** 44
**Date:** 2026-02-17

## Problem Statement

Sharing is inconsistent across the site. share_button() only works with photo IDs.
OG tags are written inline on each page without a helper. Some pages lack share
buttons entirely. The growth loop (share → preview → visit → contribute) is broken.

## Sharing Design Thesis

Every page that could prompt someone to contribute knowledge MUST be shareable with
one click, producing a link that renders a compelling preview on Facebook/iMessage/
WhatsApp and leads to a standalone page that works without login.

## Components

### 1. `og_tags(title, description, image_url, canonical_url)` Helper

Reusable function that returns Meta elements for every page's `<head>`:
- Converts all URLs to absolute (prepends SITE_URL if relative)
- Includes og:title, og:description, og:image, og:url, og:type, og:site_name
- Includes twitter:card for Twitter/X previews
- Returns tuple of Meta elements to spread into Title()

### 2. Generalized `share_button(url, title, text, style)`

Extends existing share_button() to work with any URL (not just photo_id):
- `url`: The URL to share (relative or absolute)
- `title`: Share title for native share sheet
- `text`: Share description text
- `style`: "icon" | "button" | "link" | "prominent"
- Uses `data-action="share"` (generalized from "share-photo")
- data-share-url, data-share-title, data-share-text attributes

### 3. Unified Share Script

Update `_share_script()` to handle the generalized share attributes:
- Reads title/text from data attributes
- Passes to navigator.share() on mobile
- Falls back to clipboard + toast on desktop

## Shareable Pages Matrix

| Page | Has OG Tags | Has Share Button | Needs Work |
|------|-------------|------------------|------------|
| /photo/{id} | Yes | Yes | Generalize button |
| /person/{id} | Yes | Yes | Generalize button |
| /identify/{id} | Yes | Yes (in script) | Standardize |
| /identify/{a}/match/{b} | Yes | Yes (in script) | Standardize |
| /compare | Partial | No | Add both |
| /compare/result/{id} | No (new) | No (new) | Create |
| /collection/{slug} | Partial | Yes | Complete OG |
| /tree | Partial | No | Add share |
| /connect | Partial | No | Add share |
| /map | Partial | No | Add share |
| /timeline | Partial | Yes | Verify |
| /photos | Partial | No | Add share |
| /people | Partial | No | Add share |

## Acceptance Criteria

1. og_tags() helper exists and is used on all shareable pages
2. share_button() works with any URL, not just photo IDs
3. All og:image URLs are absolute (https://...)
4. Share button visible on all pages listed above
5. Mobile share uses Web Share API; desktop uses clipboard + toast
6. All existing share tests continue to pass
7. New tests verify og_tags helper and generalized share_button

## Out of Scope

- Social share count display
- Direct social media links (Facebook, Twitter buttons)
- Share analytics/tracking
- Email sharing integration
