-- Life Events & Context Graph (PRD-011)
-- Event tagging system connecting photos, people, places, and dates.

CREATE TABLE IF NOT EXISTS life_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    location_name TEXT,
    lat NUMERIC(10,7),
    lng NUMERIC(10,7),
    event_date DATE,
    event_year INTEGER,
    date_precision TEXT DEFAULT 'year',
    created_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS event_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES life_events(id) ON DELETE CASCADE,
    identity_id UUID NOT NULL,
    role TEXT DEFAULT 'attendee',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(event_id, identity_id)
);

CREATE TABLE IF NOT EXISTS event_photos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES life_events(id) ON DELETE CASCADE,
    photo_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(event_id, photo_id)
);

CREATE INDEX IF NOT EXISTS idx_event_participants_identity ON event_participants(identity_id);
CREATE INDEX IF NOT EXISTS idx_event_photos_photo ON event_photos(photo_id);
CREATE INDEX IF NOT EXISTS idx_life_events_year ON life_events(event_year);
