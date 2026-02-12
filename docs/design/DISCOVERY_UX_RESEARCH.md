# Discovery UX Research — Heritage Photo Apps

**Last updated:** 2026-02-12

Analysis of discovery patterns in heritage photo applications and how they map to Rhodesli's features.

---

## Industry Patterns

### MyHeritage: "Photo Discoveries"

**Key insight:** Show users photos of *their* ancestors found in *other people's* collections.

- The "wow moment" is recognizing a family member you've never seen before
- Smart Matches connect records across user trees — photos surface as a byproduct
- Discovery is passive: you upload, the system finds connections and notifies you
- Colorization and animation features drive viral sharing (but are generative AI — not for us)

**What we adopt:**
- Surname-based discovery ("We found 12 photos with Capeluto family members")
- Cross-collection connections ("This person appears in both the Vida and Betty collections")
- Notification-like presentation of new discoveries

**What we skip:**
- Generative AI (colorization, animation) — violates forensic invariant #4
- Family tree matching — we don't have tree data yet

### Google Photos: Face Grouping as Delight

**Key insight:** Face grouping IS the delight. "47 photos of this person" with visual timeline is the hook.

- No explicit identification step — faces just appear as clusters
- Timeline view per person shows them aging across photos
- "Add a name" is optional, not required — unnamed groups are first-class
- People tab is the most-used feature after recents

**What we adopt:**
- Grouping before naming (merge without identifying)
- Visual timeline per identity (photos sorted by date when available)
- Unnamed groups shown prominently, not hidden
- Face count as social proof ("23 photos of this person")

**What we skip:**
- Fully automated grouping — our community needs human verification
- Pet detection — not relevant

### Ancestry: Record-to-Photo Connection

**Key insight:** Connection between photo and family tree node gives context and meaning.

- "This is your great-grandmother" with a vital record citation
- Photos gain meaning from genealogical context (dates, places, relationships)
- Hints system: "We found a record that might match your ancestor"
- Collaborative: multiple family members can attach the same person to different photos

**What we adopt:**
- Structured identity data (birth/death years, places) alongside photos
- Source citations on photos (collection, donor, newspaper)
- Hint-like suggestions ("AI thinks this might be the same person")
- Collaborative identification (multiple users can suggest names)

**What we skip:**
- GEDCOM/family tree integration (Phase F, future)
- Record matching against external databases

---

## Rhodesli's Unique Advantage

**Dense community graph.** The Sephardic Jewish families of Rhodes are densely interconnected — everyone knows (or is related to) everyone. This means:

1. **Every user can identify faces**, not just direct descendants. Claude Benatar can identify Stella Hasson because they grew up in the same community.

2. **Cross-collection recognition is high.** The same people appear across the Vida Capeluto, Betty Capeluto, and Nace Capeluto collections. A face identified in one collection immediately illuminates others.

3. **Surname recognition drives engagement.** Showing "Capeluto, Hasson, Franco, Benatar" instantly signals relevance to community members. These 13 surname variant groups (in `data/surname_variants.json`) cover most of the community.

4. **Community knowledge exceeds any single family's.** No one family has complete knowledge, but collectively the community can identify nearly everyone. The system aggregates distributed knowledge.

---

## Discovery Flow Design

### First Visit: Surname Recognition

```
"Do you recognize any of these family names?"
[Capeluto] [Hasson] [Franco] [Benatar] [Israel] [Pizante] ...
```

Tapping a surname immediately shows identified people with that name, creating an instant "I know them!" moment. This is more engaging than a generic "Welcome to our archive" message.

### Return Visit: Personalized Feed

Based on selected interest surnames, show:
1. **New discoveries** — recently identified people matching interest surnames
2. **Can you help?** — unidentified faces from photos containing known interest-surname people
3. **Collection highlights** — best photos from collections with interest-surname families

### Ongoing: Co-occurrence Surfacing

"These two unidentified people appear together in 4 photos" — leveraging the dense community graph to surface likely family members or associates.

---

## Metrics That Matter

| Metric | What it measures | Target |
|--------|-----------------|--------|
| Time to first identification | How fast a new user helps | < 5 minutes |
| Identifications per session | Engagement depth | 3+ per active session |
| Return rate (7-day) | Stickiness | > 30% of registered users |
| Cross-collection matches | System value | > 50% of identities span 2+ collections |

---

## References

- UX Principles: `docs/design/UX_PRINCIPLES.md`
- Surname Variants: `data/surname_variants.json` (13 groups)
- Future Community Design: `docs/design/FUTURE_COMMUNITY.md`
