-- Add full logging fields to gemini_api_calls (Session 92, AD-210)
-- prompt_text: The exact prompt sent to Gemini
-- full_response: Complete JSON response from Gemini
-- gedcom_context: GEDCOM context string injected into the prompt

ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS prompt_text TEXT;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS full_response JSONB;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS gedcom_context TEXT;
