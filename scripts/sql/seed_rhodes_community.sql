-- Seed the Rhodes community as the first community in the multi-tenant schema
-- Created: Session 91 Track E (2026-03-07)

INSERT INTO communities (slug, name, description, admin_emails, r2_prefix)
VALUES ('rhodes', 'Jewish Community of Rhodes',
        'Heritage photo archive for the Sephardic Jewish community of Rhodes',
        ARRAY['NolanFox@gmail.com'], 'raw_photos/')
ON CONFLICT (slug) DO NOTHING;
