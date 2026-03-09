# Session 94: Fox Family & Platform Vision — Nolan's Brain Dump

**Date:** 2026-03-09
**Session:** 94
**Source:** Direct from Nolan, verbatim capture + structured extraction

---

## Part 1: Platform Vision (Long-Term)

### The Core Thesis
Rhodesli has been successful as an ML exercise — doing something Google Photos, Amazon
Rekognition, etc. failed to do: helping explore old photos and build out community history.

### The Long-Term Vision
**Anyone could upload old media** (single photo, whole collection, eventually video) and:

1. **Create their own space** for family/community/personal photo collections
   - Example: An archive in Rezekne, Latvia could create a space where descendants of
     the Jewish community that used to live there could upload digitized old photos and
     recreate the community's history
   - Find previously unknown pictures of family
   - Unlock information (identity, relationship, context, location) in photos they have

2. **Cross-community search** — Upload a picture and search across ALL communities to
   find matches, aided by context you provide with the upload

3. **Rich context input** — Users could:
   - Add their own GEDCOM
   - Link a person in a photo with a certain community
   - Use a chat interface to dump all information about a photo or the people in it
   - Provide GEDCOM-like information via NL/chatbot

4. **Insight surfacing** — Example scenario:
   - Nolan has old photos of wife's maternal grandmother's family
   - Some people reappear (friends, family) — some known, some not
   - Someone else uploads old photos from the same area with a GEDCOM
   - System indicates a likely match based on GEDCOM context
   - Turns out wife's great-grandfather knew the other person professionally
   - Each appears in the other's photos
   - This enriches both individual and community knowledge

5. **Ultimate goal**: Search for faces across literally every old photo ever —
   archival collections, personal collections, everything

---

## Part 2: Near-Term Architecture Direction

### The "Super Collection" Concept
- What Nolan calls "collection" here supersedes the current app's "collection" concept
- Think of it as a **super collection** composed of multiple app-level collections
- Examples of super collections:
  - The Jewish Community of Rhodes (existing)
  - The Fox Family
  - A specific family branch
  - A community archive
- A photo may live in **multiple communities** (e.g., Fox family photo at a Rhodes
  community event should appear in both)

### Key Architecture Decision: Not a Clone
> "I think since eventually we'll need to figure out a way to link these, we should
> start from first principles here and find an MVP version of that and then build
> from there."

Nolan explicitly wants to avoid the "clone Rhodesli and adapt" approach. Instead:
build the multi-collection infrastructure from the start, even if the Fox MVP is simple.

### Cross-Collection Linking
- Roland Fox married Betty Capeluto → family events especially 1950s-1960s have
  lots of overlap between Fox and Rhodes collections
- Photos, people, and identities can span multiple communities
- Need to handle this without breaking existing Rhodes functionality

---

## Part 3: GEDCOM Evolution (Critical Architecture)

### Current State
- One GEDCOM (Nolan's Ancestry family tree) already contains both Capeluto AND Fox family
- GEDCOM is imported to Supabase (21,809 individuals)
- Used for Gemini date/location estimation enrichment

### Required Evolution
1. **Multiple GEDCOMs per platform** — not just one tree
2. **Multiple GEDCOM identities per person** — one person could appear in different trees
3. **Primary vs. secondary trees**:
   - Primary tree: displayed in the tree visualization
   - Secondary trees: all GEDCOM data used to enrich Gemini API calls
4. **GEDCOM upload by users** — standalone tool users might upload GEDCOMs
5. **NL GEDCOM-like input** — chatbot users provide genealogical info in natural language
6. **Version tracking** — need to track GEDCOM updates over time
7. **Cross-tree overlap** — trees can reference the same real person without breaking
   the tree visualization
8. **Confirm Supabase migration preserved GEDCOM update capability** — verify this works

### Nolan's Specific Request
> "Please confirm we are still able to update the GEDCOM well, and that we are finding
> a way to log it to a specific tree so that scales."

### Data Structure Scaling
> "In general I think as we do this we need to think about how our data structures
> can be scaled."

---

## Part 4: Fox Family Photo Collection — Specifics

### What Photos Exist
- **Quantity:** "Lots and lots" — significant collection
- **Date range:** ~120 years, starting around 1900 through modern iPhones
- **Focus period:** 1910-2000
- **Format:** Mixed — historical prints (digitized), collected online photos, uploads
  from family members

### Sources
- Large batch uploaded from Roland's brother Charlie
- Wedding pictures from Nolan's grandfather's wedding
- Family photos collected online from multiple cousins
- Other miscellaneous sources

### Metadata Available
- Nolan has extensive metadata for many photos
- Some are well-documented, others are mysteries
- Good examples where GEDCOM matching should yield enrichment
- **Notable example already shared:** Photo of Roland's father Albert Fox during WWI,
  narrowed to within ~1 year, specific location in Detroit
  (This should be in session context — verify)

### GEDCOM Status
- **Already covered** — the existing GEDCOM in the system has Fox family data
- Future: wife's family would need a separate GEDCOM

### Audience
- **Primary:** Nolan (cares a lot, deep genealogical research)
- **Secondary:** Cousins (mildly interested in well-packaged results)
- **Value prop for cousins:** Might incentivize them to:
  - Provide more context (help identify people)
  - Share more photos
  - Even if deep workflow is mostly for Nolan

### Overlap with Rhodes
- Roland Fox married Betty Capeluto
- Family events, especially 1950s-1960s, have significant overlap
- Photos from Fox collection could contain Rhodes community members

### MVP Success Criteria
> "The ability to go through the ML / human-in-the-loop workflow I have with Rhodesli
> on another photo collection and compare that to the garbage job of this I've been
> able to do in Google Photos and tried to do in Mylio would be huge."

- Organize photos that are hard to organize
- Discover stories from photos
- Impact narrative capturing and genealogical research

### Timeline
- **Priority:** Fairly high — Nolan is excited
- **Cloud consideration:** Makes sense to process in the cloud to avoid duplicate
  copies of lots of photos on old local machine
- **Scale potential:** After Fox, Nolan has ~5 other family branches (both his and
  wife's family) with enough photos for similar work

---

## Part 5: Implementation Constraints & Requests

### Must Not Break
- Existing API routes
- Existing data structures
- Current Rhodesli functionality

### Website/Domain Decision Needed
- Where does Fox family live? Same domain? Subdomain? Separate?
- How does it connect without breaking existing routes/data?

### Phased Implementation OK
> "It is also OK to have a phased implementation if it's hard to get from where we
> are to where we need to go."

### Quality Expectations
> "I expect some great work and at the end of the day getting to where we need to
> go here fairly quickly."

---

## Part 6: Open Questions to Resolve

1. **User-level vs. group-level collections?**
   - Option A: User has their own photos (personal archive)
   - Option B: Group/community has a space with shared collections
   - Option C: Both — users have personal libraries, can contribute to communities

2. **Same domain or separate instance?**
   - Must not break existing API routes or data

3. **How to handle cross-community photos?**
   - Photo in Fox collection with Rhodes people → shows in both

4. **GEDCOM multi-tree implementation** — primary/secondary model

5. **Cloud processing** — reduce laptop dependency for photo processing

6. **Standalone tools interaction** — how do standalone tool users (date estimator,
   face compare) interact with the multi-community platform?

---

## Part 7: Nolan's Answers to Architecture Questions (Round 2)

### Architecture Approach
- **Confirmed:** Approach A (community-first, `/c/{slug}`) with path to Approach B (subdomains)
- Intent was never to rebuild — build upon existing work, don't break data models
- Nolan will be the main user for first couple weeks, hopes to expand rapidly after

### Q1: Personal Library vs. Community Archive
**Answer: Community/family archive, NOT personal library.**
- MVP should feel like "The Fox Family Archive that Nolan admins"
- Differentiate from personal Google Photos where all family branches mix together
- Mixed branches → bad clustering, type I and type II face match errors
- Want to share with family members who could:
  - Upload more photos
  - Enjoy browsing
  - Help identify people
  - Provide context via chatbot
- Each community/family/town gets its own subset of photos, oriented around that group
- Still want ability to link across family branches
- Easy controls for cross-linking
- Shareable pages (like Rhodes sharing pages) specific to each community

### Q2: Domain/Branding
**Answer: Uncertain, defers to Claude's recommendation.**
- "Rhodesli" could function as a codename for the whole project
- The platform would have a Rhodes component plus a larger focus:
  - Making all the world's old photos searchable
  - Discovering identities and untold stories
  - Finding photos you didn't know were out there
- Concern: Is "Rhodesli" confusing? Most people don't know what it refers to.
  Could be a "fun sounding name" but maybe not ideal for product market fit.
- Potentially taking on **paid users in coming months** (if market fit found)
- If no market fit, still wants this software for personal use
- Expects branding might change over time depending on where traction is found
- **Key insight: potential commercialization path exists**

### Q3: Photo Ingestion Scale
**Answer: Start with a couple hundred photos at least.**
- Has several large collections ready
- Not super partial to implementation strategy, defers to best practice
- **Current 50-photo upload cap is problematic** for starting new collections
- Wants batching system or workaround for bulk upload

### Additional Feedback: Context Capture at Upload

**Critical insight:** Beyond GEDCOM, there's no good UX to capture context during
bulk upload. Currently:
- GEDCOM provides structured context
- Upload form has "source" field but that's it
- No way to bulk-select source if pictures aren't all from the same source

**Nolan's concern:** The downside of bulk upload is losing the opportunity to capture
context that would help Gemini API calls. Need to think about:
- How to capture more context during or after upload
- Context that enriches date/location estimation
- Context about known/unknown people in photos
- Metadata that aids the ML pipeline

### Q4: Pinecone for NL/LLM Chatbot
**Question from Nolan:** For the NL LLM chatbot (TOOLS-004), do we need to add
Pinecone to the architecture?
- Context: thinking about vector search across photo descriptions, context,
  GEDCOM data for the chatbot to query
- Currently no vector database (pgvector deferred until 5K+ embeddings)

---

## Part 8: Nolan's Answers to Architecture Questions (Round 3)

### Q1: Admin Model
- **Same admin (Nolan) for both Rhodes and Fox** in near term
- Eventually want to set other relatives as admin if they want to contribute
- Privacy (public/private photos) is deferred — most subjects are deceased
- Sophisticated permissions come later
- Near term: Nolan is sole admin across all communities

### Q2: Cross-Community Face Matching — Critical UX Decision
**Answer: Closest to Option A (automatic) but with nuance.**

Key requirements:
- **Same identity across communities** — Roland Fox in Rhodesli IS the same identity
  as Roland Fox in Fox Family Archive. Not a copy, not a link — same person.
- **All photos visible from identity page** — regardless of which community they're in
- **Community provenance on photos** — just like upload source is shown, each photo
  should indicate which community/super-collection it belongs to
- **Need resilience to type I and type II errors** — both will occur in cross-community
  face matching. Need a way to correct mistakes.
- **May need manual override** — ability to move from automatic to manual linking
- **Workspace transition UX concern:** If you're in Fox, click Roland, see a Rhodesli
  photo, click that photo — how does the UI indicate you've "moved" to Rhodesli?
  - Consider Notion workspace model
  - Must not be confusing
  - All photos of a person should be visible in the same identity regardless of
    community origin

**Nolan's framing:** "Essentially we'd want to see all the photos of a person in
the same identity even if they were in rhodesli, fox family, etc."

### Q2b: Community Boundary UX — Critical Constraint
**Nolan's feedback:** If you're coming to the platform for the Rhodes Jewish community,
you should NOT accidentally wander into Fox family photos unless you fully understand
what that is and intend to check it out. Otherwise, very confusing UX.

**Implication:** Community boundaries must be CLEAR and INTENTIONAL to cross.
- Browse pages are strictly community-scoped
- Identity pages show all photos BUT with clear community provenance
- Clicking a cross-community photo should have a clear "You're viewing a photo
  from the Fox Family Archive" indicator — not a silent context switch
- The landing page / entry point must be community-specific
- Navigation should reinforce which community you're in at all times

### Q3: 50-Photo Upload Cap
- **Both UX and processing concerns**
- Came up when uploading 2nd batch of 100+ photos
- Was "a bit of a pain"
- Need to review why cap was set and find better solution

## Part 9: Nolan's Answers to Architecture Questions (Round 4)

### Q1: Collection Onboarding Flow Scope
**Answer: Keep MVP simpler.** Create community + bulk upload with metadata.
- Full enrichment chat flow is a future enhancement
- Capture all the ideas, wire into roadmap/backlog/todo with breadcrumbs
- Decision doc entries needed
- Link to NL LLM chatbot (TOOLS-004) as a potential use case for context capture
- Set as a "next step" after MVP

### Q2: Photo Readiness
**Answer: Ready to start with hundreds of digitized photos.**
- Has literally thousands of photos needing scanning (ongoing effort)
- Has hundreds already digitized across multiple family branches including Fox
- Has been scanning for years + relatives have scanned their own
- Will do more scanning later but ready to start now

**TIFF/Format concern:**
- Scans are often very high quality archival TIFF files
- Need to downsize to manageable JPG/PNG
- Did this manually for Rhodesli — wants automation for Fox
- **New requirement: automated TIFF→JPG conversion in the upload pipeline**

**Google Drive/Photos import:**
- Would be ideal to automatically import from Google Drive or Google Photos albums
- Not sure how easy this is
- Fallback: download and re-upload manually
- **New requirement: explore Google Drive/Photos API integration for bulk import**
  - Google Photos API: read-only access to albums, can download media items
  - Google Drive API: list files in folder, download
  - OAuth consent screen needed
  - Could be a significant accelerator for onboarding if feasible

## Part 10: Prioritization & Session 95 Planning

### Roadmap Priority (Nolan-confirmed)
1. PRD-035 Phase 1: Fox MVP (2-3 sessions)
2. PRD-035 Phase 2: Global Identity (2 sessions)
3. TOOLS-001: Date Estimator Standalone (2-3 sessions, parallel OK)
4. PRD-035 Phase 3: Multi-GEDCOM (2 sessions)
5. TOOLS-002: ML Service Extraction (3-4 sessions)
6. PRD-035 Phase 4: Scale + Polish (1-2 sessions)
7. TOOLS-003: Face Compare Real-Time (1-2 sessions, depends TOOLS-002)
8. TOOLS-004: NL Query + Chatbot (3-5 sessions)

### Standalone Tools UX Direction
- TOOLS-001 should include **both** date estimator AND face compare standalone
- Face compare standalone is a UX/branding exercise (compare already works)
- All standalone tools should have:
  - Consistent URL paths (logically grouped)
  - Shared navigation links at the top (like Rhodes sharing area)
  - Community-agnostic language
- Think of it as a "tool suite" with a unified look

### Session 95: Autonomous Overnight Execution
- Nolan wants to kick off Session 95 overnight
- Must be fully autonomous (no interactive input needed)
- Must use worktrees/subagents for parallelization
- Must fully adhere to harness (session log, assessment, decisions, etc.)
- Quality over quantity — if parallelizing risks lower quality, do sequentially

---

## Breadcrumbs

- Platform vision feeds into: PRD-030 (multi-collection), MULTI_TENANT.md
- GEDCOM evolution feeds into: AD-160 (GEDCOM linking), AD-163 (temporal versioning)
- Fox specifics feed into: `docs/collections/fox_family_prep.md`
- Cross-community search feeds into: PRD-034 (standalone tools), TOOLS-003
- Albert Fox WWI photo: verify in session context / Albert Fox story
- Data structure scaling: DATA_MODEL.md, Supabase schema
- Upload cap issue: relates to BACKLOG upload UX items
- Context capture at upload: new requirement, not in any existing PRD
- Pinecone question: relates to TOOLS-004, pgvector evaluation
- Commercialization: new consideration, affects branding/domain decisions
- Batching system: new requirement for onboarding new collections
