# PRD-028: Contributor Notifications

**Status**: PLANNED — Session 91 (Track A). P0 implementation: in-app center + event triggers.
**Author**: Track E (Session 90b)
**Date**: 2026-03-06
**Related**: DD-003 (Discovery Notifications), OPS-001 (Custom SMTP)

---

## Problem

Contributors upload photos to the Rhodesli archive but have no way to know when
matches or identifications happen. Claude Benatar asked: "If someone uploads a
picture, how does he or she know if there's a match?"

Currently, only the admin (Nolan) sees Discoveries, match results, and identity
confirmations. Contributors are left in the dark after uploading. This breaks the
growth loop: Find -> Share -> Click -> Recognize -> **Respond** (no response path).

## User Stories

1. As a contributor who uploaded photos, I want to be notified when someone is
   identified in my photos, so I can learn who the people are.
2. As a contributor, I want to be notified when my uploaded photo gets a new
   match via auto-clustering, so I can confirm or provide additional context.
3. As a contributor, I want to see an activity feed of all changes related to
   my contributions, so I can stay engaged with the archive.

## Notification Types

### First-Order (changes to YOUR uploaded photos)
- **Identity confirmed**: A face in your photo was identified (name assigned)
- **New face match**: Auto-clustering found a match for a face in your photo
- **Location update**: A photo you uploaded received a location estimate
- **Date estimate**: A photo you uploaded received a date estimate

### Second-Order (changes to PEOPLE who appear in your photos)
- **Person merged**: Two identities were merged, one of whom appears in your photos
- **Person renamed**: Someone in your photos was renamed (display name updated)
- **New photo found**: A new photo was found containing someone from your photos

## Channels

### Email (via Resend API)
- OPS-001 already has code ready; requires RESEND_API_KEY in Railway
- **Immediate**: Identity confirmed, new strong match (>70% confidence)
- **Digest**: Low-priority events batched into daily/weekly summary

### In-App Notification Center
- Persistent, paginated list at `/notifications`
- Bell icon in header with unread count badge
- Mark-as-read (individual and bulk)
- Each notification links to the relevant photo/person page

### Push Notifications (Future)
- Web Push API for browser notifications
- Deferred until contributor base exceeds 10 active users

## Data Model

```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) NOT NULL,
    notification_type TEXT NOT NULL,
    -- Types: identity_confirmed, new_match, location_update,
    --        date_estimate, person_merged, person_renamed, new_photo_found
    title TEXT NOT NULL,
    body TEXT,
    photo_id TEXT,           -- nullable, links to photo_index
    identity_id UUID,        -- nullable, links to identities
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notifications_user_unread
    ON notifications(user_id, is_read)
    WHERE is_read = FALSE;

CREATE TABLE notification_preferences (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id),
    email_enabled BOOLEAN DEFAULT TRUE,
    in_app_enabled BOOLEAN DEFAULT TRUE,
    digest_frequency TEXT DEFAULT 'daily',
    -- Options: immediate, daily, weekly, never
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## UI

### Bell Icon (Header)
- Appears for all logged-in users
- Badge shows unread count (red dot if >0, number if >9)
- Click opens `/notifications` page

### /notifications Page
- Chronological list, newest first
- Each item shows: icon (by type), title, body preview, timestamp, link
- Unread items have a blue dot / highlight
- "Mark all as read" button at top
- Pagination (20 per page)
- Filter by type (optional, future)

### Notification Item Example
```
[Face icon] Isaac Cohen identified in your photo
  "Image 054" from Betty Capeluto Miami Collection
  2 hours ago                              [View photo ->]
```

## Implementation Phases

### P0: Database + In-App Center
- Create Supabase tables (notifications, notification_preferences)
- `/notifications` route with HTMX-powered list
- Bell icon in header with unread count
- Mark-as-read (individual + bulk)
- Manual notification creation (admin can trigger test notifications)

### P1: Event Triggers
- Hook into identity confirmation flow (save_registry post-hook)
- Hook into auto-clustering pipeline (Tier 1 auto-add triggers notification)
- Hook into merge flow
- Map events to affected users (photo uploader lookup)

### P2: Email via Resend
- Wire OPS-001 (Resend API key)
- Send immediate email for identity_confirmed events
- Email template with photo thumbnail, person name, CTA link
- Unsubscribe link per notification type

### P3: Digest + Preferences
- `/notifications/preferences` settings page
- Digest email job (daily/weekly cron via Railway)
- Batch low-priority notifications into digest
- Per-type email toggles

## Acceptance Criteria

- [ ] Logged-in users see bell icon with unread count
- [ ] /notifications shows chronological list of events
- [ ] Confirming an identity creates a notification for the photo uploader
- [ ] Auto-clustering match creates a notification
- [ ] Email sent for high-priority events (P2)
- [ ] Users can mark notifications as read
- [ ] Users can configure notification preferences (P3)

## Out of Scope

- Real-time websockets (use polling or HTMX hx-trigger="every 30s")
- Mobile push notifications (native app required)
- SMS notifications
- Notification for anonymous/non-logged-in users
- Admin notifications (admin already sees everything via Discoveries)

## Dependencies

- OPS-001: Custom SMTP / Resend API (for email channel)
- Contributor role: Currently only admin exists; notifications assume
  a contributor role that tracks who uploaded which photos
- Photo uploader tracking: Need to store which user uploaded which photo
  (currently not tracked in photo_index.json; needs Supabase column)

## Risks

- **Photo-uploader mapping**: Currently no link between photos and uploading
  users. Need to add `uploaded_by` to photo metadata or a separate table.
- **Notification volume**: If auto-clustering generates many matches, could
  flood users. Mitigate with digest mode and confidence threshold.
- **Email deliverability**: Resend handles this, but need proper SPF/DKIM
  for rhodesli.nolanandrewfox.com domain.
