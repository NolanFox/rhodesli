# Session 80 Tree UX Feedback — Must Address Next

## User Feedback (CRITICAL — do these before tree is "done")

1. **Faces not prominent enough** — face photos on person cards are too small. "Barely any of the screen is the faces." Need much larger photos.
2. **Cards too small** — each person card needs to be significantly larger. Current CARD_W=180, CARD_H=76, PHOTO_R=26. User can barely see anyone.
3. **Names hard to read** — current 12px font is too small. Names also truncate at 18 chars.
4. **No way to hide/collapse connections** — e.g., no toggle to hide siblings, hide children. Need collapse/expand per-branch or per-direction.
5. **Gender indicator missing** — should show gender on person cards when data is available (color-coded border? icon?).

## Current Constants (app/static/js/family-tree.js)
```
CARD_W = 180, CARD_H = 76
PHOTO_R = 26
V_GAP = 150
H_GAP = 50
COUPLE_GAP = 24
Name font: 12px
Date font: 10px
Name truncation: 18 chars
```

## Suggested Fixes
- Double card size: CARD_W=300, CARD_H=120, PHOTO_R=44
- Increase name font to 15-16px, date font to 12px
- Increase name truncation to 28+ chars
- Add gender color: blue border for M, pink for F, gray for unknown
- Add collapse buttons per-branch (click to hide a subtree)
- Consider vertical card orientation (photo on top, name below) for more face space

## Profile Button Issue
User reported /people/47b88468-cdb7-4140-9006-dd822f40d29b seems broken.
Worktree subagent was investigating — check if it completed and has a fix.

## Git State
Latest commit: de79ab8 (session docs)
Branch: main
Expand fix deployed and verified: 27a72a3
Worktree subagent: agent-a0660e49 (may have a branch)
