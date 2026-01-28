# Archival Gallery Styling Plan

## Current State
- FastHTML app serves crops from `app/static/crops/` at `/crops/`
- Responsive CSS Grid gallery (1-4 columns based on viewport)
- Research Notes textarea under each image (disabled placeholder)
- Archival styling: sepia filter, serif fonts, stone/amber palette

## Changes Needed

### 1. Image Padding (CSS)
Add 10% padding around crop images for breathing room.

### 2. Filename Format
Current: `603569530_803296_1_27.18_2.jpg`
Target: `{original_name}_{quality}_{idx}.jpg`

The current format already follows this pattern where:
- `603569530_803296_1` = original_name (photo ID components)
- `27.18` = quality score
- `2` = face index

No file renaming needed - the format is already correct.

## Already Complete
- [x] CSS Grid responsive layout
- [x] Research Notes field
- [x] Static file serving from app/static/crops
- [x] Archival visual styling (sepia, serif, stone colors)
