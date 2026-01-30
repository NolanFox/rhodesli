# Interaction Model

Describes user states, transitions, and navigation patterns.

---

## User Modes

### Mode: Identity Review (Default)

**Entry:** Load `/` (main workstation)
**Purpose:** Triage identities by state

**Available actions:**
- Confirm identity (PROPOSED → CONFIRMED)
- Contest identity (→ CONTESTED)
- Rename identity
- Find Similar (enters sub-mode)
- View Photo (opens modal)
- Detach face

**Exit:** Navigate to `/photos` or close browser

---

### Mode: Find Similar (Sub-mode of Identity Review)

**Entry:** Click "Find Similar" on an identity card
**Purpose:** Discover merge candidates

**Available actions:**
- Merge neighbor into current identity
- **Not Same Person** (D2): Mark neighbor as definitively NOT the same person
  - Adds bidirectional rejection to `negative_ids` with "identity:" prefix
  - Neighbor immediately removed from sidebar
  - Rejected pairs never reappear in Find Similar
- Load More neighbors (D3)
- Close sidebar (return to Identity Review)

**Exit:** Click "Close" button (B1)

**State:** Sidebar appears adjacent to identity card. Does not replace main view.

---

### Mode: Photo Context (Modal)

**Entry:** Click "View Photo" on a face card
**Purpose:** See face in original photo context

**Available actions:**
- View other faces in same photo
- Navigate to identity of any face
- Close modal

**Exit:** Click outside modal, click X, or press Escape

**State:** Modal overlays current view. Main view preserved underneath (D4).

---

### Mode: Photo Browser (Future, per D1)

**Entry:** Navigate to `/photos`
**Purpose:** Browse all photos in dataset

**Available actions:** (TBD in E2-E4)
- View photo grid
- Click photo to see faces
- Navigate to identity from face

**Exit:** Navigate to `/` or click identity link

---

## State Transitions

```
                    ┌──────────────────┐
                    │  Identity Review │
                    │    (Default)     │
                    └────────┬─────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │Find Similar │    │Photo Context│    │Photo Browser│
   │  (Sidebar)  │    │   (Modal)   │    │   (/photos) │
   └─────────────┘    └─────────────┘    └─────────────┘
          │                  │                  │
          └──────────────────┴──────────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  Identity Review │
                    └──────────────────┘
```

---

## Identity State Machine

```
PROPOSED ──confirm()──► CONFIRMED
    │                       │
    │                       │
    └──contest()──► CONTESTED ◄──contest()──┘
                       │
                       │
                    resolve()
                       │
                       ▼
                   CONFIRMED
```

**PROPOSED:** Initial state from clustering. Accepts changes.
**CONFIRMED:** Human-verified. Authoritative but reversible.
**CONTESTED:** Frozen for review. Requires explicit resolution.

---

## Navigation Invariants

1. **Back button safety:** Modals close; pages navigate. No unexpected data loss.
2. **Escape key:** Always closes topmost modal/sidebar.
3. **URL reflects mode:** `/` for review, `/photos` for browser, `/photo/{id}` for direct links (future).
4. **No orphan states:** Every mode has an explicit exit path.
