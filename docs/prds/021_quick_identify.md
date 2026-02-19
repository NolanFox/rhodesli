# PRD-021: Quick-Identify from Photo View

## Problem
When a community member identifies people in a photo (e.g., via
Facebook comment), the admin must navigate to each face's identify
page individually to enter names. For a photo with 8 identified
people, this takes ~15 minutes of clicking back and forth.

## Solution
Click any unidentified face on the photo page → inline name
input appears directly on the face → type name with autocomplete
→ confirm → face is identified. No page navigation.

## Current State (P0 — ALREADY IMPLEMENTED)

The core Quick-Identify functionality already exists as the **tag dropdown**:

| Feature | Status | Implementation |
|---------|--------|----------------|
| Inline name input on face click | DONE | Tag dropdown (main.py:8986) |
| Autocomplete search | DONE | `/api/face/tag-search` (main.py:16588) |
| Face thumbnails in results | DONE | `resolve_face_image_url()` |
| "+ Create" new identity | DONE | `/api/face/create-identity` (main.py:16867) |
| Merge into existing identity | DONE | `/api/face/tag` (main.py:16730) |
| Face overlay updates after tag | DONE | Re-renders photo view |
| Toast confirmation | DONE | OOB toast on success |
| Admin vs non-admin behavior | DONE | Admin=merge, non-admin=suggest |

## User Flow (Admin) — Existing
1. View photo page (/photo/{id}) showing faces with overlays
2. Click an unidentified face overlay
3. Tag dropdown appears with search input
4. Type a name — autocomplete shows matching identities with thumbnails
5. Click existing identity → merge, OR click "+ Create" → new identity
6. Photo view re-renders showing the new name
7. Click next face and repeat

## Gap: Sequential "Name These Faces" Mode (P1 — THIS SESSION)

The existing flow requires clicking each face individually. For photos
with many unidentified faces (Carey Franco's 8-person photo), this is
still ~2 clicks per face × 8 = 16 clicks. With sequential mode:

### User Flow (Sequential Mode)
1. Admin sees "Name These Faces (8 unidentified)" button on photo
2. Clicks button → first unidentified face highlights + tag dropdown opens
3. Types name → autocomplete → select → face identified
4. Tag dropdown automatically moves to next unidentified face
5. Progress shows "3 of 8 identified"
6. After last face or press "Done": mode exits
7. All 8 names entered without manual face clicking

## Requirements

### P1: Sequential Mode (this session)
1. "Name These Faces" button on photos with 2+ unidentified faces
2. Activates sequential mode: first unidentified face auto-highlighted
3. After naming one face, auto-advance to next unidentified face
4. Progress indicator: "3 of 8 identified"
5. "Done" button / Escape to exit mode
6. Visual highlight on the currently active face
7. Works in both full photo page and photo modal

### P2: Polish (future)
8. Undo last identification (5-second window)
9. Bulk name entry from text paste
10. Show ML match suggestions inline

### Deferred
- Non-admin inline identification (uses annotation/proposal flow)
- Mobile-optimized touch targets
- Facebook comment import

## Technical Approach
- Sequential mode state managed via HTMX + Hyperscript
- "Name These Faces" button triggers first face's tag dropdown
- After successful tag POST, response includes trigger to open next face's dropdown
- Progress tracked client-side via data attributes
- Exit mode: removes highlighting, closes any open dropdown

## Out of Scope
- Modifying existing tag dropdown UX (it works well as-is)
- Non-admin inline identification
- The /identify/{id} page (unchanged)
