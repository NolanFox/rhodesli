# Logic Audit Notes

Audit performed: 2026-01-28

---

## 1. Padding Math Audit (`core/crop_faces.py`)

### Summary: PASS (with minor observations)

The 10% padding logic in `add_padding()` is mathematically correct and handles edge cases properly.

### Implementation Review

```python
x1_padded = max(0, int(x1 - pad_x))
y1_padded = max(0, int(y1 - pad_y))
x2_padded = min(width, int(x2 + pad_x))
y2_padded = min(height, int(y2 + pad_y))
```

**Clamping is correct:**
- `max(0, ...)` prevents negative coordinates
- `min(width/height, ...)` prevents overflow past image bounds

### Edge Cases Verified

| Scenario | Handled? | Notes |
|----------|----------|-------|
| Face at origin (0,0) | ✅ | Clamps to 0 |
| Face at image edge | ✅ | Clamps to width/height |
| Float coordinates | ✅ | `int()` truncates safely |
| Negative bbox from detector | ✅ | `max(0, ...)` handles it |
| Asymmetric images | ✅ | Uses `height, width` separately |

### Edge Cases NOT Tested (Low Risk)

1. **Tiny bounding boxes (<10px)**: Padding rounds to 0, resulting in no padding. Unlikely with real face detections.

2. **Degenerate boxes (zero area)**: Would produce 0x0 crop. Only happens with malformed data.

3. **Face at exact corner touching (0,0,w,h)**: Clamping handles this, but no explicit test.

**Recommendation:** These are theoretical edge cases. Current test coverage is sufficient for production use.

---

## 2. Keyboard Accessibility Audit (`app/main.py`)

### Summary: FAIL - Critical Issue Found

### Critical Issue: Textarea is Disabled

```python
Textarea(
    placeholder="Research notes...",
    disabled=True,  # <-- BLOCKS ALL INTERACTION
    cls="..."
)
```

**Impact:**
- Users CANNOT focus the field with Tab
- Users CANNOT type in the field
- The feature is completely non-functional

**Severity:** HIGH

**Fix:** Remove `disabled=True` or change to `readonly=True` if edit-blocking is intentional.

### Secondary Issues

| Issue | Severity | Description |
|-------|----------|-------------|
| No focus ring | MEDIUM | Missing `focus:ring-2 focus:ring-amber-500` or similar. Keyboard users can't see focus state. |
| No label element | LOW | Placeholder is not a substitute for `<label>`. Screen readers need proper labeling. |
| No `name` attribute | LOW | Data won't be submitted if form functionality is added later. |

### Recommended Fix (for reference)

```python
Textarea(
    placeholder="Research notes...",
    # disabled=True,  # REMOVE THIS
    name="notes",
    cls="w-full mt-2 p-2 text-sm font-serif bg-amber-50 border border-stone-300 "
        "resize-y h-16 placeholder:italic placeholder:text-stone-400 "
        "focus:outline-none focus:ring-2 focus:ring-amber-600 focus:border-amber-600"
)
```

---

## Action Items

1. **[HIGH]** Remove `disabled=True` from Research Notes textarea
2. **[MEDIUM]** Add Tailwind focus ring classes for keyboard visibility
3. **[LOW]** Consider adding proper `<label>` elements for accessibility
