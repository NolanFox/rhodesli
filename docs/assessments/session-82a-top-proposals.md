# Top 5 UX Proposals for Rhodesli (Session 82a)

After an extensive UX audit of the current platform and research into competitors like MyHeritage, Ancestry, and FamilySearch, the following five features have been identified as providing the highest UX ROI for the Rhodesli Heritage Archive.

## 1. Click-to-Target AI Bounding Boxes
**Problem**: The current freehand box-drawing tool for facial tagging is cumbersome, especially on mobile devices or edge-of-photo faces.
**Solution**: Utilize the underlying ML bounding box detections. Users click anywhere on a face, and a precise, resizable square bounding box snaps into place automatically. This drastically reduces friction for crowdsourcing tags.

![AI Bounding Box Mockup](/Users/nolanfox/rhodesli/docs/assessments/mockups/mockup_ai_bounding_box.png)

## 2. Masonry Adaptive Grids
**Problem**: Historical photos vary wildly in aspect ratio (tall portraits, wide panoramic group shots). Forcing them into rigid CSS square aspect-ratio grids chops off heads and contextual details in the thumbnail view.
**Solution**: Implement a dynamic, justified masonry layout for the `/photos` view. This maintains the original aspect ratio of every vintage photo while fitting them together seamlessly like a puzzle (similar to Google Photos or FamilySearch Memories).

![Masonry Grid Mockup](/Users/nolanfox/rhodesli/docs/assessments/mockups/mockup_masonry_grid.png)

## 3. "Missing Info" Tabular List View
**Problem**: Power users attempting to systematically audit and clean up the archive struggle because the visual grid view makes it hard to see what metadata is missing at a glance.
**Solution**: Introduce a dense, tabular "List View" for photos. Empty cells for 'Name', 'Date', and 'Location' act as explicit "Add Info" CTAs, allowing rapid, bulk data entry.

![Missing Info Table Mockup](/Users/nolanfox/rhodesli/docs/assessments/mockups/mockup_missing_info_table.png)

## 4. Integrated "LifeStory" Vertical Timelines
**Problem**: Currently, photos and life events on the Person Dashboard are somewhat disconnected.
**Solution**: Weave a person's photos chronologically together with textual life events (birth, marriage, immigration) on a central vertical timeline axis. This structural storytelling approach provides significantly more historical context than a simple image gallery.

![Vertical Timeline Mockup](/Users/nolanfox/rhodesli/docs/assessments/mockups/mockup_vertical_timeline.png)

## 5. Interactive Radial Family Tree
**Problem**: Discovering relatives requires clicking back and forth between Person pages.
**Solution**: Implement a toggleable, interactive D3/Canvas radial graph view centered on the current person. This visually displays connections (spouses, siblings, parents) expanding outward, providing a highly engaging map of their immediate family network.

![Radial Tree Mockup](/Users/nolanfox/rhodesli/docs/assessments/mockups/mockup_radial_tree.png)
