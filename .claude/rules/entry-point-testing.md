---
paths:
  - "app/main.py"
  - "tests/**"
---

# Entry-Point Testing Rule

Our #1 recurring bug category: UI components work from Path A but break from Path B.

## Rule

For every multi-path UI component:

1. **Enumerate ALL entry points** — How many ways can a user reach this component?
2. **Write a test for EACH entry point** — Not just the primary one
3. **Verify parameter consistency** — Same component must receive same params from all paths

## Common Multi-Path Components

- **Compare Modal**: Reachable from AI suggestions, Find Similar, Focus mode
- **Lightbox**: Reachable from identity card, search results, collection browse, Compare modal
- **Identity Card**: Reachable from search, sidebar, photo overlay click, Compare modal name link
- **Photo Context**: Reachable from lightbox, identity card "View Photo", Compare modal

## Before Shipping

Ask: "How many ways can a user reach this?" If >1, need >1 test path.

## Pattern

```python
@pytest.mark.parametrize("entry_point", [
    "/api/compare?face_a=X&face_b=Y",           # From AI suggestion
    "/api/find-similar/X",                        # From Find Similar
    "/api/focus/compare?identity=X&suggestion=Y", # From Focus mode
])
def test_compare_modal_from_all_entries(entry_point, client):
    resp = client.get(entry_point)
    assert resp.status_code == 200
    assert "compare" in resp.text.lower()
```

Reference: Lessons 39, 45, 46, 63
