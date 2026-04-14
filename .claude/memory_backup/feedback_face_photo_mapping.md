---
name: Always verify face-to-photo mapping before data mutations
description: Face IDs and photo IDs use different ID schemes (inbox_* vs SHA256). Must verify which face is in which photo via photo_faces table + SHA256 hash before any split/merge/detach operation.
type: feedback
---

When splitting clusters or moving faces between identities, ALWAYS verify the face-to-photo mapping by:
1. Query `photo_faces` table for the face_id → get photo_id (inbox-style)
2. Query `photos` table for the photo_id → get path
3. Compute SHA256 hash of the basename to get the URL-style photo_id
4. Cross-reference with the user's photo URL

**Why:** Session 114 post-session: Split the WRONG face off Person 4063. The investigation doc had descriptions like "P2 = close-up arm-in-arm with Esther" but the user was referencing photo `dbc16e6d973cc900` (URL-style ID). I assumed P2 was the Esther photo based on the description, but P2's SHA256 hash was `5a6f8a7c90928724`, not `dbc16e6d973cc900`. The correct face was P3 (`inbox_fb4b65ccecfe` = SHA256 `dbc16e6d973cc900`).

**How to apply:**
- NEVER assume face-to-photo mapping from descriptions alone
- Always compute SHA256 hash: `hashlib.sha256(basename.encode()).hexdigest()[:16]`
- When user provides a photo URL, extract the photo_id from the URL path and match against the hash
- Add this verification step to any future cluster-splitting code (UX-130)
- This is the SECOND mistake in this operation (first: missed identity_overrides table). Both stem from insufficient verification before mutation.
