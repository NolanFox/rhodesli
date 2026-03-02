# Divergent Ideation (Session 82a)

## Discovery & Navigation
1.  **Global Command Palette / Search Bar**: A sticky header search bar for instantly finding people by name, photos by location, or specific tags across the entire archive.
2.  **Masonry Adaptive Grids**: Replace the rigid square crop grid on the "Photos" page with a justified masonry layout to better display the varying aspect ratios of vintage historical photos without chopping off heads.
3.  **"Surprise Me" Module**: A randomized "Discover a Memory" interaction on the homepage to encourage serendipitous exploration of deep-archive items.
4.  **Power-User Keyboard Shortcuts**: Implement left/right arrows for photo navigation, '/' to focus search, and 'F' to toggle face overlays, accompanied by a discoverable help modal.
5.  **Robust Mobile Hamburger Menu**: Fix the critical mobile header overlap on Timeline/Compare pages by unifying all top-level navigation into a clean, slide-out hamburger menu on viewports < 768px.
6.  **Interactive Radial Family Tree**: From the Person page, offer a toggleable D3/Canvas-based radial graph view to visually display connections (parents, siblings, spouses) interactively.
7.  **"Recently Viewed" Breadcrumb Trail**: A section at the bottom of the People and Photos index pages to help users seamlessly resume their previous browsing session.
8.  **Advanced Filtering Sidebar**: A rich filtering pane on the Photos page (filter by specific decade slider, presence of unidentified faces, specific locations, or ML collection clusters).
9.  **Infinite Scroll / Progressive Loading**: Replace traditional pagination jumps with smooth, staggered progressive loading as the user scrolls down the People or Photos grids.
10. **Persistent Visual Breadcrumbs**: Clear hierarchical trails at the top of every detail page (e.g., `Archive > 1920s > Rhodes > Wedding Photo`) to prevent users from getting disoriented during deep dives.

## Photo Context & Storytelling
11. **Before & After Enhancement Slider**: An interactive slider on the Photo page comparing the original raw scan with any AI-enhanced, upscaled, or colorized versions.
12. **Audio "Narrative" Snippets**: Allow family members to record and attach short (30-second) audio voiceovers to a photo, explaining the backstory or identifying individuals via spoken word.
13. **Historical Context Sidebar**: Next to a photo, display dynamic contextual facts (e.g., "In 1924, when this was taken, the population of Rhodes was X, and Y historical event had just occurred").
14. **Integrated "LifeStory" Vertical Timelines**: Interweave a person's chronological life events (birth, immigration, marriage) directly with their photos in a unified vertical narrative on the Person page.
15. **Inline Map View Toggle**: A toggle on the Person page that switches the photo grid into a geographical heatmap, showing exactly where in the world their timeline unfolded.
16. **Cinematic "Ken Burns" Slideshows**: A dedicated view mode for Collections or a Person's gallery that automatically pans and zooms slowly across photos for a passive viewing experience.
17. **"Identify Mode" Focus State**: A toggle on the Photo page that heavily dims the background and highlights all *unidentified* faces with a glowing, pulsing ring to draw attention.
18. **Semantic Pin Drops (Non-Face Tagging)**: Allow users to pin contextual tooltips onto specific parts of a photo (e.g., highlighting a specific building, a uniform badge, or an heirloom piece of jewelry).
19. **Relational Context Labels**: Beneath identified faces, dynamically textually describe the relationship based on the viewer's context or intra-photo context (e.g., "Alberto, standing next to his brother Isaac").
20. **"On This Day in History" Module**: A homepage feature surfacing photos taken, or people born, on the exact current calendar month/day.

## Crowdsourcing & Identification
21. **"Missing Info" Tabular List View**: A dedicated power-user view (similar to MyHeritage) that displays photos/people in a dense table, using empty cells as explicit CTAs to fill in missing dates or locations in bulk.
22. **Click-to-Target AI Bounding Boxes**: Replace manual freehand drawing for tagging with a system where clicking anywhere on a face automatically generates a precise, resizable square bounding box based on underlying ML detection.
23. **Contributor Gamification Profile**: Reward users with badges or a lightweight leaderboard for "Most Faces Identified" or "Most Biographical Details Added" to incentivize crowdsourcing.
24. **"Low Confidence" Suggestion Mode**: Allow users to submit an identification with a "Not Sure, But It Might Be..." flag, logging it as a suggestion rather than a definitive assertion for community review.
25. **Dedicated "Help Needed" Landing Page**: A triage queue that specifically surfaces the top 50 photos possessing the highest count of clear, high-resolution faces that remain unidentified.
26. **Categorized AI Rejection Reasons**: When a user rejects an AI match proposal, provide quick radio buttons for "Wrong Gender," "Too Young," or "Not Related" to better train the feedback loop.
27. **"Guess Who?" Micro-Interactions**: Small, inline widgets on the homepage or sidebar presenting a single random cropped face, asking "Do you recognize this person?" to capture passing attention.
28. **Specialized "Share for Help" Button**: A share action that generates an OpenGraph card specifically optimizing the crop on the *unidentified* faces along with a plea for identification, rather than just sharing the whole photo.
29. **Contextual Discussion Threads**: A lightweight commenting UI directly beneath each photo where the community can debate conflicting identifications or share circumstantial evidence prior to a formal tag.
30. **One-Click Bulk Tag Confirmation**: For admins, an inbox view that groups community-suggested face tags, allowing the admin to approve or reject dozens of pending suggestions with a single click.
