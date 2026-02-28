# Timeline Slider & Photo Scrubber UX Research

**Date:** 2026-02-28
**Context:** Research for Rhodesli photo archive timeline scrubber.
**See also:** [reactive-tree-patterns.md](reactive-tree-patterns.md) for animation/transition code patterns.

---

## The 5 Best Examples

### 1. Google Photos Timeline Scrubber

**What it is:** Right-side fast-scroller with floating date indicator for 100K+ photos.

**What makes it great:**
- **Variable-speed scrubbing** — drag farther left from scrollbar for finer control. At far left = day-by-day. At scrollbar = years fly by.
- **Virtualized grid** — only renders visible items + buffer. Absolutely positioned with `translate3d`; DOM changes don't trigger reflow.
- **Progressive loading** — tiny 25% quality placeholders first, then thumbnails (80x larger), then medium previews on pause. Decoding off main thread.
- **Date-range indexing** — client requests "images between June-Aug 2015" instead of sequential pagination. Enables instant jumps.
- **Batch network requests** — groups thumbnail fetches (10/batch), prioritizes visible over prefetch.

**Steal for Rhodesli:** Date indicator floating alongside scrollbar showing decade/year. Variable-speed scrub. Absolutely positioned grid. Progressive image loading (blur placeholder -> crop thumbnail).

Sources: [How Google Photos Makes Infinite Scroll Feel Infinite](https://medium.com/@amitbvp13/how-google-photos-makes-infinite-scroll-feel-infinite-b2208ff03bb9), [Building the Google Photos Web UI](https://medium.com/google-design/google-photos-45b714dfbed1), [Building the Image Grid](https://medium.com/@danrschlosser/building-the-image-grid-from-google-photos-6a09e193c74a)

---

### 2. MyHeritage Family Tree Timeline

**What it is:** Horizontal timeline mapping family lifespans as colored bars along a time axis.

**What makes it great:**
- **Lifespan bars** — horizontal bar per person from birth to death. Living = squared right edge. Deceased = rounded + age-at-death.
- **Color-coded branches** — maternal vs paternal in distinct colors. Instant visual parsing.
- **Historical overlays** — hatched rectangles mark WWI, WWII, etc. Family events in world context.
- **Generation slider** — 3 to 9 generations. More gens = zoomed-out timeline.
- **Hover cards** — photo, name, relationship, links to edit/view/research.
- **Error detection** — red dots flag chronological impossibilities (parent died before child's birth).

**Steal for Rhodesli:** Lifespan bars (we have birth/death years for 21K+ GEDCOM individuals). Historical overlays (Rhodes deportation 1944, emigration waves). Color-coded branches. Generation depth slider.

Sources: [MyHeritage Timeline](https://education.myheritage.com/article/exploring-your-family-tree-timeline/), [Introducing the Timeline](https://blog.myheritage.com/2022/03/introducing-the-family-tree-timeline/)

---

### 3. Clyfford Still Museum Interactive Timeline

**What it is:** 17-foot-wide, 4-station multi-touch timeline presenting an artist's life in context.

**What makes it great:**
- **Multi-user** — 4 people explore different timeline segments simultaneously.
- **Dual-layer** — personal biography on one track, world/art history on another, with visual links between.
- **Mechanical metaphor** — dial-driven "Exhibit Film Story Viewers" for documentary content. Physical interaction inspires engagement.
- **Scale = intuition** — proportional year-to-space mapping creates natural navigation.

**Steal for Rhodesli:** Dual-track timeline (family events + historical events). "Viewers" for different family branches. Physical-feeling interactions (snap-to-decade, momentum scrolling).

Source: [Belle & Wissell — Clyfford Still Museum](https://bwco.info/work/still-interactive-timeline/)

---

### 4. Recap / AgeLapse Face Timelapse Apps

**What it is:** Mobile apps that align faces by eye position and create scrub-able aging timelapses.

**What makes it great:**
- **Auto-stabilization on eyes** — transitions between photos from different years are seamless.
- **AI-curated selection** — picks "best" selfie per period, not every photo.
- **Scrub interaction** — drag slider, face morphs between years via crossfade at face level.
- **Multiple profiles** — each person gets their own stabilized timeline.

**Steal for Rhodesli:** Eye-aligned face stabilization for crossfade between decades (we have InsightFace coordinates). Curated "best photo per era." Scrub slider that morphs between aligned face crops.

Sources: [Recap](https://apps.apple.com/us/app/recap-photo-timelapse/id6670143752), [AgeLapse](https://apps.apple.com/us/app/agelapse/id6503668205)

---

### 5. FamilySearch Timeline + Map

**What it is:** Dual-panel view — chronological event list paired with interactive map.

**What makes it great:**
- **Vertical list + map** — events by date, map pins for each location. Click event -> map zooms.
- **Icon vocabulary** — birth (oval), death (flower), marriage (ring), burial (tombstone), residence (house).
- **Historical context** — up to 8 historical events on same timeline.
- **Research prompts** — shows where records exist you haven't attached. Timeline as research tool.
- **Bidirectional navigation** — click timeline -> map zooms. Click pin -> timeline highlights.

**Steal for Rhodesli:** Bidirectional linked panels (timeline + photo gallery). Icon vocabulary. "Research prompt" concept (where photos might exist that we lack). Map (Rhodes, NYC, Buenos Aires).

Sources: [FamilySearch Timeline](https://www.familysearch.org/en/help/helpcenter/article/what-is-the-timeline-or-map-in-family-tree), [FamilySearch Timeline Features](https://familylocket.com/familysearch-timeline-features-help-you-research-like-a-pro/)

---

## Recommended Architecture for Rhodesli

```
+------------------------------------------------------------------+
|  [1900]----[1920]----[1940]----[1960]----[1980]     year markers |
|       ●         ●         ●●        ●                photo dots  |
|  <====================[THUMB]====================>   range input |
+------------------------------------------------------------------+
|                                                                  |
|  +--------+  +--------+  +--------+  +--------+                 |
|  | face 1 |  | face 2 |  | face 3 |  | face 4 |   photos from  |
|  | crop   |  | crop   |  | crop   |  | crop   |   selected era  |
|  +--------+  +--------+  +--------+  +--------+                 |
+------------------------------------------------------------------+
```

**Implementation:**
1. Horizontal `<input type="range">` at viewport bottom (video scrubber style)
2. Year markers with decade labels as tick marks
3. Photo density dots showing where photos cluster in time
4. Scrubbing updates gallery — crossfade between eras via CSS opacity
5. Snap-to-decade with CSS `scroll-snap-type`
6. For a specific person: show their face crops aging through decades
7. Use HTMX `hx-trigger="input changed delay:100ms"` for server-side filtering

**Performance budget:**

| Operation | Target | Method |
|-----------|--------|--------|
| Slider scrub | 0ms input lag | Native range input + CSS transitions |
| Photo crossfade | 60fps | CSS opacity only (compositor layer) |
| Era gallery load | < 200ms | HTMX swap with skeleton placeholders |

---

## Additional Sources

- [Dribbble Timeline Slider Designs](https://dribbble.com/search/timeline-slider)
- [History Associates — Multidimensional Timelines](https://www.historyassociates.com/multidimensional-timelines/)
- [MyHeritage PedigreeMap](https://blog.myheritage.com/2016/07/introducing-pedigreemap-an-interactive-map-of-your-family-history/)
- [GSAP ScrollTrigger](https://gsap.com/docs/v3/Plugins/ScrollTrigger/)
- [CSS Scroll-Driven Animations — Smashing Magazine](https://www.smashingmagazine.com/2024/12/introduction-css-scroll-driven-animations/)
- [Scroll-Driven Animations Spec](https://scroll-driven-animations.style/)
