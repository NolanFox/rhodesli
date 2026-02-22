# PRD-022: Photo Detective UX

**Status**: In Progress (Session 61)
**Author**: Nolan Fox + Claude Code
**Priority**: P1

## Concept

Gemini analyzing a photo is like a detective examining evidence. The UX should
expose this process — showing evidence categories, reasoning chains, and how
verified facts improve estimates.

## Key UX Elements

1. **Evidence Cards**: Each evidence category (clothing, architecture, text,
   faces) gets a card showing what was detected and how it contributed
2. **Confidence Meter**: Visual indicator of overall estimate confidence
3. **Model Badge**: "Analyzed with Gemini 3.1 Pro" — users see the value
4. **Progressive Refinement Indicator**: When verified facts improve
   an estimate, show what changed and why

## Where Evidence Appears

- `/estimate` page: Full detective display for uploaded or archive photos
- `/photo/{id}` page: Estimate badge + expandable evidence section
- Compare results: Per-photo estimate info

## Evidence Categories

| Category | Icon | Source |
|----------|------|--------|
| Print/Physical | camera | Print format cues |
| Fashion/Grooming | clothing | Clothing analysis |
| Environment | building | Architecture, vegetation |
| Technology | monitor | Objects, vehicles |
| Cultural context | cultural | Community-specific signals |

## Success Criteria

1. Evidence cards render for each category with icon and description
2. Model badge shows which Gemini model was used
3. Photo pages show estimate badge when estimate exists
4. Progressive refinement shows before/after when estimate improves
