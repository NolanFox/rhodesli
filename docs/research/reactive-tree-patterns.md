# Reactive Tree & Animation Patterns

**Date:** 2026-02-28
**Context:** Technical patterns for making Rhodesli tree/gallery interactions feel reactive and smooth.
**See also:** [timeline-slider-research.md](timeline-slider-research.md) for UX examples.

---

## 1. CSS Crossfade Between Photos

Stack two images absolutely, transition opacity. Compositor-only = 60fps guaranteed.

```css
.photo-crossfade-container {
  position: relative;
  overflow: hidden;
}
.photo-crossfade-container img {
  position: absolute;
  top: 0; left: 0;
  width: 100%; height: 100%;
  object-fit: cover;
  transition: opacity 0.4s ease-out;
}
.photo-crossfade-container img.active { opacity: 1; }
.photo-crossfade-container img.inactive { opacity: 0; }
```

**Why it works:** `opacity` is compositor-only. GPU handles it. Zero layout/paint cost.

---

## 2. Image Scrubber with Range Input

```javascript
const slider = document.getElementById('year-slider');
const photosByYear = { 1920: {...}, 1935: {...}, 1944: {...} };

function findNearestPhoto(year) {
  const years = Object.keys(photosByYear).map(Number).sort((a,b) => a-b);
  return years.reduce((prev, curr) =>
    Math.abs(curr - year) < Math.abs(prev - year) ? curr : prev
  );
}

let currentYear = null;
slider.addEventListener('input', (e) => {
  const year = parseInt(e.target.value);
  const nearest = findNearestPhoto(year);
  if (nearest !== currentYear) {
    // Swap active/inactive classes for CSS crossfade
    stage.querySelector('img.active')?.classList.replace('active', 'inactive');
    stage.querySelector(`img[data-year="${nearest}"]`)?.classList.replace('inactive', 'active');
    currentYear = nearest;
  }
});
```

---

## 3. CSS Transform Transitions (Never Layout Properties)

**Critical:** Never animate `width`, `height`, `top`, `left`, `margin`, `padding`. These trigger reflow.

```css
/* BAD — layout recalc every frame */
.tree-node { transition: left 0.3s, top 0.3s; }

/* GOOD — compositor-only, GPU-accelerated */
.tree-node {
  transition: transform 0.3s ease-out, opacity 0.3s ease-out;
  will-change: transform;  /* add before animating, remove after */
}
.tree-node.moving { transform: translate(120px, -60px); }
```

**Rendering pipeline:**
1. Recalculate Style
2. **Layout** (reflow) — width/height/margin/position
3. **Paint** — color/background/shadow
4. **Composite** — transform/opacity only

Goal: keep everything in step 4.

---

## 4. requestAnimationFrame for Custom Animations

```javascript
function animateNodes(nodes, startPos, endPos, duration = 300) {
  const startTime = performance.now();
  function frame(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
    nodes.forEach((node, i) => {
      const x = startPos[i].x + (endPos[i].x - startPos[i].x) * eased;
      const y = startPos[i].y + (endPos[i].y - startPos[i].y) * eased;
      node.style.transform = `translate(${x}px, ${y}px)`;
    });
    if (progress < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}
```

---

## 5. D3 Enter/Update/Exit with Transitions

```javascript
const nodes = svg.selectAll('.tree-node')
  .data(tree.descendants(), d => d.data.id);

// ENTER: appear at parent position, animate to final
nodes.enter().append('g')
  .attr('class', 'tree-node')
  .attr('transform', `translate(${source.x0},${source.y0})`)
  .style('opacity', 0)
  .merge(nodes)
  .transition().duration(400).ease(d3.easeCubicOut)
  .attr('transform', d => `translate(${d.x},${d.y})`)
  .style('opacity', 1);

// EXIT: collapse to parent, then remove
nodes.exit().transition().duration(300).ease(d3.easeCubicIn)
  .attr('transform', `translate(${source.x},${source.y})`)
  .style('opacity', 0).remove();
```

**Easing choices:**
- `easeCubicOut` — fast start, gentle stop. Use for **entering** elements.
- `easeCubicIn` — gentle start, fast exit. Use for **leaving** elements.
- `easeCubic` — slow-fast-slow. General purpose.

---

## 6. Optimistic UI Updates

```javascript
function expandNode(nodeId) {
  // 1. IMMEDIATELY show skeleton children
  renderChildren(nodeId, createSkeletonNodes(3));
  animateExpand(nodeId);

  // 2. Fetch real data
  fetch(`/api/tree/expand/${nodeId}`)
    .then(r => r.json())
    .then(data => replaceWithRealNodes(nodeId, data.children))
    .catch(() => {
      collapseNode(nodeId);
      showToast('Could not load family members');
    });
}
```

**Pattern:** Apply visual change immediately. Confirm with server. Revert on failure.

**Pre-fetch on hover** (bonus):
```javascript
node.addEventListener('mouseenter', () => {
  const link = document.createElement('link');
  link.rel = 'prefetch';
  link.href = `/api/tree/expand/${nodeId}`;
  document.head.appendChild(link);
});
```

---

## 7. Skeleton Loading States

```css
.skeleton-node {
  background: linear-gradient(90deg, #e0e0e0 25%, #f0f0f0 50%, #e0e0e0 75%);
  background-size: 200% 100%;
  animation: skeleton-pulse 1.5s ease-in-out infinite;
  border-radius: 8px;
}
@keyframes skeleton-pulse {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

**Rules:** Match actual content dimensions (prevent layout shift). Pulse for < 3 seconds. Shape hints content type (circle = face, rectangle = name).

---

## 8. Easing Reference

| Easing | cubic-bezier | Use for |
|--------|-------------|---------|
| ease-out | `(0, 0, 0.58, 1)` | Enter, expand |
| ease-in | `(0.42, 0, 1, 1)` | Exit, collapse |
| snappy | `(0.2, 0, 0, 1)` | Toggles, clicks |
| gentle (Material) | `(0.4, 0, 0.2, 1)` | Most transitions |

**Duration:** 200-400ms UI transitions. 100-200ms micro-interactions. Always `ease-out` for entering, `ease-in` for leaving.

---

## 9. CSS Scroll-Driven Animations (Progressive Enhancement)

```css
/* Photos fade in as they enter viewport — no JS */
.photo-card {
  animation: fadeSlideIn ease-out;
  animation-timeline: view();
  animation-range: entry 0% entry 100%;
}
@keyframes fadeSlideIn {
  from { opacity: 0; transform: translateY(40px) scale(0.95); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
```

**Support:** Chrome 115+. Firefox behind flag. Safari not yet. Use as enhancement with JS fallback.

---

## 10. Snap-to-Decade

```css
.timeline-track {
  scroll-snap-type: x mandatory;
  overflow-x: scroll;
  display: flex;
}
.decade-marker {
  scroll-snap-align: start;
  min-width: 100%;
  flex-shrink: 0;
}
```

```javascript
function snapToDecade(decade) {
  document.querySelector(`[data-decade="${decade}"]`)
    .scrollIntoView({ behavior: 'smooth', inline: 'start' });
}
```

---

## Sources

- [D3 Transitions In Depth](https://www.d3indepth.com/transitions/)
- [D3 Easing Functions](https://github.com/d3/d3-ease)
- [D3 Collapsible Tree](https://observablehq.com/@d3/collapsible-tree)
- [Optimistic UI Patterns](https://simonhearne.com/2021/optimistic-ui-patterns/)
- [Skeleton Screens 101 — NN/g](https://www.nngroup.com/articles/skeleton-screens/)
- [Skeleton Loading Design — LogRocket](https://blog.logrocket.com/ux-design/skeleton-loading-screen-design/)
- [60 FPS Animations with CSS3](https://medium.com/outsystems-experts/how-to-achieve-60-fps-animations-with-css3-db7b98610108)
- [Web Animation Performance — freeCodeCamp](https://www.freecodecamp.org/news/web-animation-performance-fundamentals/)
- [Easing Functions Cheat Sheet](https://easings.net/)
- [Understanding Easing Curves](https://joshcollinsworth.com/blog/easing-curves)
- [Easing Functions — Smashing Magazine](https://www.smashingmagazine.com/2021/04/easing-functions-css-animations-transitions/)
- [CSS Scroll-Driven Animations — Smashing Magazine](https://www.smashingmagazine.com/2024/12/introduction-css-scroll-driven-animations/)
- [60FPS Smooth Scrolling with rAF](https://gist.github.com/drwpow/17f34dc5043a31017f6bbc8485f0da3c)
- [img-comparison-slider](https://github.com/sneas/img-comparison-slider)
- [GSAP ScrollTrigger](https://gsap.com/docs/v3/Plugins/ScrollTrigger/)
