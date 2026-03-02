# Competitor UX Analysis

## Overview
This report analyzes the photo and storytelling user experiences of major genealogy platforms (MyHeritage, Ancestry, FamilySearch) to identify UX patterns applicable to Rhodesli.

## MyHeritage
*   **Photo Grid Layout**: Uses a dual-view strategy. Provides a visual "Grid View" and a heavily structured "List View" designed specifically for auditing missing metadata (dates, places, face tags).
*   **Face Tagging UX**: Bulk AI Tagging. The "Photo Tagger" groups identical faces using facial recognition, allowing users to confirm tags in bulk or hover over faces to "Add Name."
*   **Life Timeline**: Features a horizontal "Family Timeline" with cards, as well as an AI-driven "Photo Storytime" that animates photos into a video narrative.
*   **Crowdsourcing / Missing Info**: The List View employs a tabular format where empty cells act as explicit CTAs for users to fill in missing names or dates.

## Ancestry
*   **Photo Grid Layout**: Photos are integrated directly into trees via "Galleries" linked to specific ancestors, using a standard rectangular grid augmented with hints.
*   **Face Tagging UX**: Users click a face to generate a square box, then search their tree. Facial recognition suggestions are integrated directly into the "Storytelling" flow.
*   **Life Timeline**: "LifeStory" is a prominent vertical timeline that weaves vital records (birth, residence) together with photos and personal anecdotes.
*   **Crowdsourcing / Missing Info**: Uses a passive hint system ("Shaking Leaf" icon) to suggest photos and records from other user trees to fill gaps.

## FamilySearch
*   **Photo Grid Layout**: The "Memories" section employs a justified/masonry adaptive grid that handles varying photo aspect ratios without cropping (similar to Google Photos).
*   **Face Tagging UX**: Shifted from manual circular drawing to an intuitive "Click-to-Target" system where clicking a face generates a resizable square box, improving accuracy.
*   **Life Timeline**: The "Time Line" on person profiles displays an integrated chronological list of life events, documents, and photos.
*   **Crowdsourcing / Missing Info**: Operates on a collaborative global tree where anyone can tag photos. Uses explicit "Research Suggestions" and "Record Hints" modules.

## Key Takeaways for Rhodesli
1.  **The "List View" Advantage**: MyHeritage's use of a tabular list view specifically for spotting missing information is highly effective for power users auditing archives.
2.  **Modernizing Tagging**: The modern pattern is moving away from freehand drawing to clicking a detected face or generating a default resizable box (like FamilySearch and MyHeritage).
3.  **Justified Grids**: A masonry-style grid (FamilySearch) is vastly superior for historical archives containing many non-standard or tall portrait photos, avoiding awkward square cropping.
4.  **Integrated Timelines**: Ancestry's vertical "LifeStory," which interweaves photos with demographic events, is the gold standard for chronological narrative and would complement Rhodesli's timeline.
