-- Session 104b: Prevent anchor_ids/candidate_ids/negative_ids from being stored
-- as JSON strings instead of JSONB arrays.
--
-- Root cause: Python client double-serializes Python strings to JSONB text.
-- CHECK constraint rejects any write where these columns aren't arrays.
--
-- Run in Supabase SQL Editor.

ALTER TABLE identities
  ADD CONSTRAINT anchor_ids_is_array CHECK (jsonb_typeof(anchor_ids) = 'array'),
  ADD CONSTRAINT candidate_ids_is_array CHECK (jsonb_typeof(candidate_ids) = 'array'),
  ADD CONSTRAINT negative_ids_is_array CHECK (jsonb_typeof(negative_ids) = 'array');
