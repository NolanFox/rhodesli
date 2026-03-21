# UI Specification: Historical/Archival Image Gallery

Research findings for implementing a responsive image grid with a historical/archival aesthetic using FastHTML and Tailwind CSS.

## FastHTML Patterns

### Tailwind CSS Integration

FastHTML integrates with Tailwind CSS via the `hdrs` parameter. Disable the default Pico CSS when using Tailwind:

```python
from fasthtml.common import *

app, rt = fast_app(
    pico=False,  # Disable Pico CSS
    hdrs=(
        Script(src="https://cdn.tailwindcss.com"),
        # Optional: custom Tailwind config
        Script("""
            tailwind.config = {
                theme: {
                    extend: {
                        fontFamily: {
                            serif: ['Georgia', 'Cambria', 'Times New Roman', 'serif'],
                        }
                    }
                }
            }
        """),
    ),
    static_path=str(Path(__file__).resolve().parent / "static"),
)
```

### Responsive Grid Pattern

FastHTML uses Python functions to generate HTML. The current gallery already uses this pattern:

```python
# Grid container with cards
cards = [Div(..., cls="tailwind-classes") for item in items]
gallery = Div(*cards, cls="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4")
```

Key Tailwind grid classes:
- `grid` - Enable CSS Grid
- `grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4` - Responsive columns
- `gap-4` - Consistent spacing (1rem)
- `auto-rows-fr` - Equal height rows

---

## Tailwind CSS: Historical/Archival Aesthetic

### Color Palette

**Warm neutrals for aged paper effect:**

| Purpose | Class | Hex |
|---------|-------|-----|
| Page background | `bg-stone-100` | #f5f5f4 |
| Card background | `bg-stone-50` | #fafaf9 |
| Darker accent | `bg-stone-200` | #e7e5e4 |
| Aged paper | `bg-amber-50` | #fffbeb |
| Warm cream | `bg-amber-100` | #fef3c7 |

**Text colors:**

| Purpose | Class | Hex |
|---------|-------|-----|
| Headings | `text-stone-800` | #292524 |
| Body text | `text-stone-700` | #44403c |
| Muted/captions | `text-stone-500` | #78716c |
| Warm accent | `text-amber-900` | #78350f |

### Typography

**Serif fonts for historical feel:**
- `font-serif` - Georgia, Cambria, Times New Roman
- `font-bold` - Strong headings
- `italic` - Emphasis, captions
- `tracking-wide` - Spaced headings
- `leading-relaxed` - Comfortable reading

**Drop cap effect (for descriptions):**
```html
<p class="first-letter:text-5xl first-letter:font-serif first-letter:float-left first-letter:mr-2">
```

### Borders

**Classic archival borders:**
- `border border-stone-300` - Subtle card borders
- `border-2 border-stone-400` - Stronger dividers
- `border-t border-stone-200` - Horizontal rules
- `border-b-2 border-stone-800` - Newspaper-style underlines

**Vintage frame effect:**
```
border border-stone-300 shadow-sm ring-1 ring-stone-200 ring-offset-2 ring-offset-stone-50
```

### Image Effects

**Sepia filter for vintage photos:**
- `sepia` - Full sepia tone (100%)
- `sepia-[.5]` - Partial sepia (custom)
- `hover:sepia-0` - Remove on hover (reveal original)
- `transition-all duration-300` - Smooth transition

**Combined vintage effect:**
```
filter sepia brightness-95 contrast-105 hover:sepia-0 hover:brightness-100 transition-all duration-500
```

**Faded/aged photo effect:**
```
opacity-90 saturate-50 sepia
```

### Card Component Design

**Archival card styling:**
```
bg-stone-50 border border-stone-300 shadow-sm p-4
hover:shadow-md hover:border-stone-400 transition-all
```

**Image container:**
```
overflow-hidden border border-stone-200 bg-stone-100
```

**Quality badge (archival label style):**
```
inline-block px-2 py-1 text-xs font-serif italic
bg-amber-100 text-amber-900 border border-amber-200
```

---

## Complete Component Classes

### Page Layout
```
min-h-screen bg-stone-100 p-4 md:p-8
```

### Header
```
text-center mb-8 border-b-2 border-stone-800 pb-4
```

### Title
```
text-3xl md:text-4xl font-serif font-bold text-stone-800 tracking-wide
```

### Subtitle
```
text-lg font-serif italic text-stone-600 mt-2
```

### Gallery Grid
```
grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 max-w-7xl mx-auto
```

### Face Card
```
bg-stone-50 border border-stone-300 p-3 shadow-sm
hover:shadow-md hover:border-stone-400 transition-all duration-200
```

### Face Image
```
w-full h-auto sepia hover:sepia-0 transition-all duration-500
border border-stone-200
```

### Quality Score
```
mt-2 text-sm font-serif italic text-stone-600
```

### Notes Textarea
```
w-full mt-2 p-2 text-sm font-serif bg-amber-50
border border-stone-300 focus:border-amber-400 focus:ring-1 focus:ring-amber-200
placeholder:text-stone-400 placeholder:italic resize-y
```

---

## Accessibility Considerations

1. **Contrast**: Sepia tones reduce contrast. Ensure text remains readable:
   - Use `text-stone-800` or darker on light backgrounds
   - Avoid light text on sepia-toned backgrounds

2. **Hover states**: Provide visual feedback beyond just sepia removal:
   - Add `ring` or `shadow` changes
   - Use `transition` for smooth effects

3. **Focus states**: Ensure keyboard navigation is visible:
   - `focus:ring-2 focus:ring-amber-400 focus:ring-offset-2`

---

## Sources

- [FastHTML Gallery](https://gallery.fastht.ml/)
- [FastHTML-Gallery GitHub](https://github.com/AnswerDotAI/FastHTML-Gallery)
- [Tailwind CSS Sepia](https://kombai.com/tailwind/sepia/)
- [Tailwind CSS Typography Plugin](https://github.com/tailwindlabs/tailwindcss-typography)
- [Tailwind CSS Colors](https://tailwindcss.com/docs/colors)
- [FastHTML + Tailwind Integration](https://www.seancdaly.com/posts/fasthtml_tailwind/)
- [CSS Sepia Filter Guide](https://codelucky.com/css-sepia-filter/)
- [Vintage Photo Effects with CSS](https://medium.com/swlh/image-effects-css-c3fb65c1583e)
