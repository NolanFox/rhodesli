---
paths:
  - "app/main.py"
  - "app/auth.py"
  - "core/storage.py"
---

# Discovery UX Principles

These 10 principles govern all user-facing UX decisions. Read before any UI work.

1. **Wow moment within 30 seconds**: New visitors must see a compelling face match or historic photo immediately. No blank states, no "nothing to see here."

2. **Faces must be LARGE**: Minimum 64px in lists, 192px+ in review/focus mode. Users can't identify family members from 32px thumbnails. Use `get_best_face_id()` to show highest-quality crop.

3. **No dead ends**: Every page has a clear next action. If the inbox is empty, redirect to Help Identify. If Help Identify is empty, show People. Always provide a path forward.

4. **Enhancement is UX-only**: Photo enhancement (GFPGAN, CLAHE, etc.) NEVER touches ML pipeline. Enhanced images are for human viewing comfort only. See AD-037.

5. **Mobile portrait is the default viewport**: Design for 375px first, enhance for desktop. Bottom navigation, hamburger sidebar, vertical stacking in focus mode.

6. **Keyboard shortcuts need undo**: Every destructive action (merge, reject, skip) must have an undo path. Z-key for undo, toast notifications showing what happened and how to reverse it.

7. **Names are complicated**: Support first/last/maiden/aliases/generation qualifiers. Never assume "FirstName LastName" format. Surname variants must be searched bidirectionally (AD-028).

8. **Show best photo first, never hide poor quality**: Use quality scoring (AD-038) to surface the best thumbnail, but never filter out low-quality faces from any view. A blurry 1920s match is better than no match.

9. **Skip = end of queue, not removal**: Skipped faces stay in the system and participate in future ML matching (AD-024). They rotate to the back of the review queue.

10. **Warm, personal, curious**: This is a family heritage tool, not a BI dashboard. Use serif fonts for headings, warm colors (amber, indigo), contextual descriptions that explain WHY a match is suggested.
