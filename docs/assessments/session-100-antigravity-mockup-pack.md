# Session 100 Antigravity Mockup Pack

**Date:** 2026-03-12
**Author:** Antigravity
**Context:** Creating targeted UI mockups to solve the "speed-run tagging" and dense multi-face gallery bottlenecks for Fox Family.

## 1. Batch Cluster Confirmation (`Mockup A: The Cluster Queue`)

**The Problem:** The user currently has to tag 15 separate photos of "Roland Fox" one single click at a time, navigating between each photo.
**The Solution:** A dedicated review surface that groups highly similar faces and asks for bulk confirmation.
**Mockup Design:**

````html
<!-- docs/assessments/mockups/session-100/mockup-a-cluster-queue.html -->
<div class="max-w-4xl mx-auto p-6 space-y-8">
  <header class="flex justify-between items-end border-b pb-4">
    <div>
      <h2 class="text-xs font-mono uppercase tracking-widest text-slate-500">Fox Family / Identify</h2>
      <h1 class="text-2xl font-serif">Are these Roland Fox?</h1>
    </div>
    <div class="flex gap-2">
      <button class="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-sm rounded transition-colors">Select All</button>
      <button class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded transition-colors">Confirm Selected (12)</button>
    </div>
  </header>
  
  <div class="grid grid-cols-4 sm:grid-cols-6 gap-4">
    <!-- Selected state -->
    <div class="relative group cursor-pointer ring-2 ring-blue-500 rounded-md overflow-hidden">
      <img src="..." class="w-full aspect-square object-cover" alt="Face crop">
      <div class="absolute inset-0 bg-blue-500/20"></div>
      <div class="absolute top-2 right-2 bg-blue-500 text-white rounded-full p-1"><CheckIcon /></div>
    </div>
    
    <!-- Unselected state -->
    <div class="relative group cursor-pointer hover:ring-2 hover:ring-slate-300 rounded-md overflow-hidden">
      <img src="..." class="w-full aspect-square object-cover opacity-90 group-hover:opacity-100" alt="Face crop">
    </div>
    
    <!-- Repeated for remaining faces in the cluster... -->
  </div>
  
  <footer class="flex justify-between items-center text-sm text-slate-500 pt-8 border-t">
    <button class="hover:text-red-600 transition-colors">Ignore Entire Group</button>
    <span>Showing 15 highly-confident matches</span>
  </footer>
</div>
````

**Improvements vs Current:** 
- Click count to tag 15 photos drops from ~45 clicks (nav, click tag, confirm) to 2 clicks (Select All, Confirm).
- Keeps the user entirely within the identify context.

---

## 2. Photo-Level Auto-Advance review (`Mockup B: The Speed Loop`)

**The Problem:** Tagging a face from a photo drops the user back to a gallery view, destroying momentum. Ignoring a background face takes too many clicks.
**The Solution:** A locked "Triage UI" that auto-advances through faces within a photo, then auto-advances to the next photo in the queue.
**Mockup Design:**

````html
<!-- docs/assessments/mockups/session-100/mockup-b-speed-loop.html -->
<div class="flex h-screen bg-black text-white">
  <!-- Left: Main Photo Area -->
  <div class="flex-1 relative flex items-center justify-center p-8">
    <img src="..." class="max-h-full max-w-full object-contain" alt="Current photo">
    <!-- Active face highlighted with a box -->
    <div class="absolute border-2 border-yellow-400 shadow-[0_0_0_9999px_rgba(0,0,0,0.6)]" style="top:30%; left:40%; width:15%; height:20%;"></div>
  </div>

  <!-- Right: Triage Sidebar -->
  <div class="w-80 bg-slate-900 border-l border-slate-800 p-6 flex flex-col">
    <div class="text-xs font-mono uppercase tracking-widest text-slate-500 mb-8">Review Queue (142 remaining)</div>
    
    <div class="flex-1 flex flex-col justify-center gap-6">
      <img src="..." class="w-32 h-32 rounded-full mx-auto border-4 border-yellow-400 object-cover" alt="Focus face crop">
      <h3 class="text-center font-serif text-xl">Who is this?</h3>
      
      <!-- Combobox for naming -->
      <input type="text" placeholder="Start typing a name..." class="w-full bg-slate-800 border-slate-700 text-white rounded p-3" autofocus>
      
      <div class="text-center text-slate-500 text-sm">or</div>
      
      <!-- 1-click ignore -->
      <button class="w-full py-3 border border-slate-700 hover:bg-slate-800 rounded text-slate-300 transition-colors">
        Ignore Background Stranger
      </button>
    </div>
  </div>
</div>
````

**Improvements vs Current:**
- Click count drops from ~4 clicks per face to 1 keyboard-driven entry + Enter.
- "Ignore Stranger" is a 1-click explicit action, instantly purging noise.
- The visual overlay keeps the source photo constantly in context without context-switching to a dedicated person page.

---

## 3. Dense Multi-Face Expanded View (`Mockup C: The Wrap Grid`)

**The Problem:** The current plan proposes a horizontal scroll-snap strip for secondary faces. For a wedding photo with 20 faces, this requires tedious linear scrolling on a mobile device to find the right face.
**The Solution:** A progressively disclosed grid that expands downwards, prioritizing usability over compact vertical height.
**Mockup Design:**

````html
<!-- docs/assessments/mockups/session-100/mockup-c-wrap-grid.html -->
<div class="border rounded-lg p-4 bg-white shadow-sm max-w-2xl">
  <!-- Hero Section -->
  <div class="flex gap-4 items-start pb-4 border-b">
    <img src="..." class="w-20 h-20 rounded object-cover" alt="Hero face">
    <div class="flex-1">
      <h3 class="font-serif text-lg font-medium">Charlotte Fox</h3>
      <p class="text-sm text-slate-500">Appears in Date Unknown</p>
    </div>
    <div class="px-2 py-1 bg-slate-100 text-xs font-mono rounded">14 Faces</div>
  </div>

  <!-- Expanded Grid Section (Replaces the horizontal strip) -->
  <div class="pt-4">
    <h4 class="text-xs uppercase tracking-wider text-slate-500 mb-3">Other People in Photo</h4>
    
    <!-- Wrapping Grid -->
    <div class="grid grid-cols-5 sm:grid-cols-7 gap-2">
      <!-- Tagged Face -->
      <div class="group relative aspect-square">
        <img src="..." class="w-full h-full object-cover rounded" alt="Secondary face">
        <div class="absolute inset-x-0 bottom-0 bg-black/60 text-white text-[10px] truncate px-1 py-0.5 rounded-b opacity-0 group-hover:opacity-100 transition-opacity">
          Roland
        </div>
      </div>
      
      <!-- Untagged Face -->
      <div class="group relative aspect-square">
        <img src="..." class="w-full h-full object-cover rounded ring-2 ring-yellow-400" alt="Untagged face">
        <div class="absolute inset-0 bg-yellow-400/20 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
          <span class="bg-yellow-400 text-black text-xs font-bold px-1.5 py-0.5 rounded">Tag</span>
        </div>
      </div>
      
      <!-- Repeated for all 13 remaining faces... -->
    </div>
    
    <!-- Optional: Lens/Source Photo Affordance -->
    <div class="mt-4 text-right">
      <button class="text-sm text-blue-600 hover:text-blue-800 font-medium transition-colors">
        View Full Source Photo &rarr;
      </button>
    </div>
  </div>
</div>
````

**Improvements vs Current:**
- All 14 secondary faces are instantly visible on a mobile device without swiping.
- "Tag" actions for unresolved faces are explicitly surfaced on hover (desktop) or tap (mobile).
- Added the "View Full Source Photo" lens escape hatch requested in the plan review.

---

## Conclusion & Recommendation

**The Risk / Over-Design Trap:**
The biggest trap is building a complex drag-and-drop face-merging tool (like full Lightroom). Rhodesli does not need complete graph clustering yet. It just needs *bulk confirmation* and *auto-advance*.

**Recommendation:**
Implement **Mockup B (The Speed Loop)** first. 
1. `Mockup A` (Cluster Queue) is highly effective, but it requires new backend endpoints to serve clusters of faces.
2. `Mockup C` (Wrap Grid) solves a presentation problem on existing views.
3. `Mockup B` solves the core *workflow momentum* problem immediately. By simply modifying the existing Identify route to accept a `?queue_id=X` query parameter, we can auto-advance the user to the next face the moment they hit "Submit" or "Ignore", transforming the app from a CMS into a triage engine.
