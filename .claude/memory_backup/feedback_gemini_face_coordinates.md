---
name: Always include face bounding box coordinates in Gemini calls
description: When sending photos to Gemini for face analysis, ALWAYS include bounding box coordinates to specify which face to analyze. Without coordinates, Gemini may analyze the wrong person in group photos.
type: feedback
---

When calling Gemini for any face-related analysis (comparison, alignment, identification), ALWAYS include the bounding box coordinates of the target face.

**Why:** Session 114 post-session: Sent group photos to Gemini without coordinates. Gemini 3.1 Pro analyzed the wrong person in the photo, producing a completely wrong verdict ("different" when the correct answer was ambiguous). The existing `face_alignment.py` already uses `_build_coordinate_bridge()` to do this correctly — the pattern was right there but was ignored for the ad-hoc comparison.

**How to apply:**
- Get bounding box from embeddings.npy (field: `bbox` = [x1, y1, x2, y2])
- Include in prompt: "The target face is located at coordinates [x1, y1] to [x2, y2] in this [W x H] pixel image"
- For comparison prompts: specify coordinates for EACH photo
- Reference: `app/face_alignment.py` `_build_coordinate_bridge()` pattern
- This applies to ALL Gemini face calls — ad-hoc scripts, batch analysis, in-app tools

**First occurrence:** Person 2491 vs Harry Fox comparison (2026-03-18). Gemini 3.1 Pro said "different" because it analyzed the wrong person in the group photo.
**Associated UX feedback:** UX-131 (in-app comparison tool), UX-130 (cluster splitting)
