# Face Comparison Tools: Competitive Research

**Date:** 2026-02-17

## Industry Standard UX Pattern

Every major face comparison tool follows the same core pattern:

1. **TWO upload slots** side by side (drag-and-drop or click)
2. **One action button:** "Compare"
3. **Result:** similarity percentage + same/not same verdict
4. Some tools add: age/gender/emotion breakdown per face

### Competitors Analyzed

| Tool | Upload UX | Results | Unique Feature |
|------|-----------|---------|----------------|
| FacePair | Two side-by-side slots | Percentage | Minimal, fast |
| ToolPie | Drag-and-drop zones | Percentage + verdict | Free, no signup |
| ProFaceFinder | Two upload areas | Detailed breakdown | Feature-level similarity |
| VisageHub | Clean two-zone layout | Eyes/nose/jawline scores | Feature decomposition |
| Amazon Rekognition | API-first, console demo | Confidence + bounding boxes | Enterprise-grade |

### Key UX Insights

1. **Upload is ALWAYS the primary action, above the fold** — no competitor buries upload below a gallery
2. **Side-by-side layout** makes the comparison intent immediately obvious
3. **Results show a single clear number** (e.g., "87% similar") — not raw distance scores
4. Better tools (VisageHub) **break down similarity by feature** (eyes, nose, jawline) — adds credibility
5. **Privacy messaging** is common ("photos deleted after processing")
6. **No competitor offers "search an existing archive"** — this is Rhodesli's unique differentiator

## What Rhodesli Does Differently

Rhodesli's compare isn't "are these two faces similar?" — it's **"does this face match anyone in our archive of 662 faces from the Jewish community of Rhodes?"**

This is fundamentally more powerful because:
- The archive has **historical context** (dates, collections, names)
- Matches **connect to real people** and family trees
- Results lead to **identification and contribution**
- The archive **grows over time** — every upload makes future comparisons better

## Weaknesses in Current Rhodesli Compare

1. Upload buried at bottom of page, below 46 face thumbnails
2. 46-face grid is overwhelming and unclear in purpose
3. No clear CTA after finding a match
4. Uploaded photos aren't saved — one-time use
5. No way to share a comparison result
6. Two use cases not distinguished clearly enough
7. Match labels misleading ("very likely" at 57%)

## Recommendations

1. **Upload-first layout** — two zones at top, archive search collapsed below
2. **Smart behavior** — one photo triggers "Search Archive", two triggers "Compare"
3. **Calibrated labels** — based on actual kinship calibration data (AD-067)
4. **Result permalinks** — shareable with OG tags
5. **Auto-save uploads** — grow the archive from every comparison
6. **Action-oriented CTAs** — "Share with family", "Name this person", "Try another photo"
