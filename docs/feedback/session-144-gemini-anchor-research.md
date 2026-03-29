# Session 144: Gemini Anchor Photo Research — Albert Fox Timeline

**Date**: 2026-03-28
**Photos**: Oval portrait (Photo B), Detroit group (Photo A), Pioneer Maccabees (Photo C)
**Photo C URL**: `inbox_fox-charlie-001_12_01635_p_13akf5twbc0904`

## Key Discovery: Pioneer Maccabees Poster

Gemini enhanced the poster behind Albert in Photo C and identified:
- **Text**: "PIONEER / MACABEES / DETROIT / JULY 2X"
- **Knights of the Maccabees**: Major fraternal benefit society, world HQ in Detroit
- **"Pioneer Tent"**: Local chapter name — Albert was a member
- **Ring on left hand**: Likely fraternal/signet ring (Maccabees membership), not wedding ring
- **Timeline constraint**: July 1911-1914 (Albert age 19-22)

## Census-Constrained Timeline

| Photo | Location | Date | Albert's Age | Evidence |
|-------|----------|------|-------------|----------|
| C (Maccabees) | Detroit | July 1911-1914 | 19-22 | Poster text, census data (in NY for 1910 census) |
| A (Outdoor group) | Detroit? | 1917-1918 | 25-26 | Pre-enlistment, more mature features |
| B (Oval portrait) | Ohio? | 1919-1920 | 27-28 | Post-war, engagement/wedding era |

## Census Context
- 1910 census: Albert still in parents' NY household
- 1915 NY State Census: Only younger siblings (Isreal 16, Jacob 12) with parents Meyer and Bessie
- Albert left NY between 1910-1915, arrived Detroit

## Physical Aging Progression (Gemini's Analysis)
- Photo C: Softer, rounder, boyish face. Loose un-styled hair. Teenager/early 20s.
- Photo A: Firmer jawline, young adult, heavily pomaded hair. Mid-20s.
- Photo B: Fully mature adult features. Late 20s.

## Feature Ideas Extracted from This Workflow

### 1. Anchor-Based Timeline Reasoning (AD-233 extension)
- **What happened**: User manually gave Gemini 3 photos + GEDCOM context, asked for chronological ordering
- **Feature**: Admin tool to select 2+ photos of same person, send to Gemini with GEDCOM context, get chronological ordering with reasoning
- **Value**: Each new photo comparison tightens the timeline for ALL photos of that person
- **Implementation**: `multi_pass.py` already has scaffold. Need multi-image Gemini call with structured output.

### 2. Visual Detail Enhancement + OCR
- **What happened**: User asked Gemini to enhance a poster, decode text, research historical context
- **Feature**: "Enhance & Analyze Detail" button on photo page — crop a region, enhance, OCR, research
- **Value**: Text on signs, posters, documents in photos becomes searchable metadata
- **Implementation**: Crop region selector + Gemini vision enhancement prompt + store findings in date_labels

### 3. Census/Historical Record Cross-Reference
- **What happened**: User provided 1910/1915 census data to constrain Gemini's dating estimate
- **Feature**: Allow admin to paste external evidence (census records, city directories) as context for Gemini
- **Value**: Each piece of external evidence narrows the date window
- **Implementation**: Text input field on photo page → appended to Gemini context → stored in date_labels.evidence
- **Maps to**: TOOLS-005 Estimate v2 (text context parameter)

### 4. Physical Aging Model
- **What happened**: Gemini tracked aging progression (jawline, hair style, facial fullness) across 3 photos
- **Feature**: Automated facial aging trajectory per person — given confirmed dates, extrapolate to undated photos
- **Value**: Each dated photo of a person helps date ALL their other photos
- **Implementation**: PRD-059 Phase 4 (identity inference via age trajectory + GEDCOM + co-occurrence)

### 5. Fraternal/Social Network Detection
- **What happened**: Poster text revealed Albert was member of Knights of Maccabees
- **Feature**: Tag photos with organizational affiliations discovered through visual evidence
- **Value**: Groups people by social networks, not just family — important for community archives
- **Implementation**: New controlled_tag category "organization:" + text_signage analysis

### 6. Iterative Context Building
- **What happened**: Each new piece of information (census, poster text, ring analysis) improved all estimates
- **Feature**: "Add evidence" workflow — admin adds facts, system re-evaluates all related photos
- **Value**: Progressive refinement — the archive gets smarter with each human contribution
- **Implementation**: date_refinement_history (already in Phase 4 schema) + trigger re-evaluation on new evidence

## BACKLOG Items
- ANCHOR-002: Multi-photo chronological ordering tool (extends AD-233)
- DETAIL-001: Visual detail enhancement + OCR for signs/posters
- EVIDENCE-001: Census/external record context input (maps to TOOLS-005)
- AGING-001: Physical aging trajectory model (maps to PRD-059 Phase 4)
- SOCIAL-001: Organization/affiliation tagging from visual evidence
- EVIDENCE-002: Iterative evidence accumulation workflow
