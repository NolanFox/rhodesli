---
paths:
  - "app/main.py"
  - "docs/feedback/*"
description: Strategic context for current development priorities
---

# Session Priorities: The Shareable Moment

## Strategic Context (from Claude Benatar feedback, Feb 2026)
- Community adoption is the #1 challenge, not technology
- The "wow moment" (photo context with face overlays) must be the first thing people see
- Sharing is the primary growth mechanism — every photo page is a potential entry point
- Institutional partnerships (museum, archives) provide credibility + steady users

## Current Focus: Viral Loop
The public photo viewer at `/photo/{id}` is the cornerstone of the sharing strategy:
1. Someone shares a photo link (WhatsApp, email, social media)
2. Recipient sees the museum-like page with face overlays and person cards
3. The CTA at the bottom drives them to explore or contribute
4. OG meta tags make the link preview compelling (rich image + description)

## Key Implementation Patterns
- `public_photo_page()` in app/main.py — the shareable page renderer
- `SITE_URL` env var for absolute URLs in OG tags
- Web Share API with clipboard fallback for share button
- Event delegation via `data-action` for all action buttons (share, flip, download)
- Front/back flip uses CSS 3D transforms with `perspective: 1200px`

## What's Next
- Analytics: track which photos get shared, which drive return visits
- Enhancement toggle: make photos look better for sharing (UX-only, no ML modification)
- Institutional outreach: museum/archive partnerships for credibility
