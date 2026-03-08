# PRD-033: Date Estimator Standalone Product

**Author:** Session 92
**Date:** 2026-03-07
**Status:** Draft
**Session:** 92 (PRD only)
**References:** PRODUCT-004 in ROADMAP.md

---

## Problem Statement

Rhodesli has built a capable photo date estimation pipeline using Gemini
vision analysis. This pipeline:

- Analyzes clothing, hairstyles, photographic techniques, paper quality
- Cross-references GEDCOM biographical data when available
- Produces decade-level estimates with confidence scores
- Has processed 296 photos with community-validated results

This capability has standalone commercial value beyond the Rhodesli archive.
Genealogists, archivists, antique dealers, and history enthusiasts regularly
need to date old photographs, and no good automated tool exists.

## Market Opportunity

### Target Users

| Segment | Size | Willingness to Pay |
|---------|------|-------------------|
| **Genealogists** | ~30M in US alone | High — pay for Ancestry, MyHeritage |
| **Archivists** | ~100K institutions | Medium — grant-funded, budget-conscious |
| **Antique dealers** | ~500K in US | High — dating affects pricing |
| **History enthusiasts** | Millions | Low-medium — hobbyists |
| **Photo restoration services** | ~50K businesses | High — adds value to service |

### Competitive Landscape

| Tool | Approach | Limitations |
|------|----------|-------------|
| Manual estimation | Expert knowledge | Slow, expensive, not scalable |
| Google Lens | Visual search | No date estimation capability |
| ChatGPT/Claude vision | General LLM | No specialized pipeline, inconsistent |
| **Rhodesli Date Estimator** | Specialized Gemini pipeline | Purpose-built, validated results |

## Product Vision

### Name Options
- **PhotoDate** — simple, descriptive
- **TimeFrame** — evocative, memorable
- **DateMyPhoto** — playful, searchable

### Core Value Proposition
Upload an old photo. Get an estimated date range with visual evidence
explaining why (clothing analysis, photographic technique, paper type).

## Revenue Model

### Tier Structure

| Tier | Price | Features |
|------|-------|----------|
| **Free** | $0 | 3 photos/month, basic date range |
| **Pro** | $9.99/month | 50 photos/month, detailed analysis, evidence cards |
| **API** | $0.10/photo | Programmatic access, bulk processing |
| **Enterprise** | Custom | Volume pricing, custom models, on-prem |

### Unit Economics

| Metric | Value |
|--------|-------|
| Gemini API cost per photo | ~$0.01-0.02 (Flash) or ~$0.05 (Pro) |
| Gross margin at $0.10/photo | ~80-90% |
| Break-even (infrastructure) | ~500 Pro subscribers |

## Architecture

### System Design
```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Frontend   │────▶│   API Layer   │────▶│   Gemini    │
│  (Next.js)   │◀────│  (FastAPI)    │◀────│   Vision    │
└─────────────┘     └──────────────┘     └─────────────┘
                          │
                    ┌─────┴──────┐
                    │  Supabase   │
                    │  (storage,  │
                    │   auth,     │
                    │   billing)  │
                    └────────────┘
```

### Extraction Plan

Code to extract from Rhodesli:

| Module | Source | Standalone Version |
|--------|--------|--------------------|
| Gemini prompt | `rhodesli_ml/gemini_config.py` | `date_estimator/prompts.py` |
| Response parsing | `rhodesli_ml/gemini_extraction.py` | `date_estimator/parser.py` |
| Evidence cards | `app/estimate_routes.py` | `date_estimator/ui/cards.py` |
| API logging | `app/main.py` (gemini_api_calls) | `date_estimator/logging.py` |

### GEDCOM Enhancement (Premium Feature)

The Rhodesli pipeline is uniquely powerful when GEDCOM data is available:
- Cross-references estimated dates against known life events
- Narrows date ranges using biographical constraints
- This becomes a premium upsell: "Upload your family tree for better results"

## User Flows

### Flow 1: Free User
1. User lands on homepage with compelling before/after examples
2. User uploads a photo (drag-and-drop)
3. System analyzes via Gemini Flash (~2-3s)
4. User sees: estimated date range, confidence level, 2-3 evidence points
5. CTA: "Get detailed analysis with Pro" or "Try another photo (2 remaining)"

### Flow 2: Pro User
1. User uploads photo
2. System analyzes via Gemini Pro (~3-5s)
3. User sees: full evidence card breakdown (clothing, technique, paper, context)
4. User can download analysis report as PDF
5. Analysis saved to history for future reference

### Flow 3: API User
1. Developer POSTs image to `/api/v1/estimate`
2. Response: JSON with date range, confidence, evidence array
3. Rate limited per API key

## Technical Constraints

- **Gemini API dependency** — single point of failure. Mitigate with retry +
  fallback to Flash if Pro fails.
- **Cost scaling** — must monitor Gemini costs per user tier.
- **No training data leakage** — Rhodesli archive photos must NOT be used
  as examples in the standalone product without community consent.
- **Privacy** — uploaded photos must be deleted after analysis (free tier)
  or retained only with user consent (pro tier).

## Out of Scope (v1)

- Mobile app
- Batch upload (> 1 photo at a time)
- Integration with Ancestry/MyHeritage
- Custom model training
- Multi-language support
- On-premises deployment

## Implementation Plan

### Phase 1: Extract + Validate (1 session)
- Extract Gemini pipeline to standalone package
- Validate results match Rhodesli's existing output
- Set up FastAPI service with single endpoint

### Phase 2: Frontend + Auth (1-2 sessions)
- Build upload + results page
- Supabase auth integration
- Free tier rate limiting

### Phase 3: Monetization (1 session)
- Stripe integration for Pro tier
- API key management
- Usage tracking and billing

### Phase 4: Launch
- Landing page with examples
- Product Hunt launch
- Genealogy community outreach

## Success Metrics

| Metric | Target (3 months) |
|--------|-------------------|
| Monthly active users | 1,000 |
| Pro conversions | 5% of free users |
| API customers | 10 |
| Monthly revenue | $500 |
| Cost per analysis | < $0.03 average |
