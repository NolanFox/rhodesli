/**
 * family-tree.js
 * Standalone wrapper for the family-chart library.
 * Loads f3 globally and initializes the tree using Editorial Archival styles.
 */

window.setupFamilyTree = function (data, containerSelector, rootPersonId) {
    const container = document.querySelector(containerSelector);
    if (!container || !data || data.length === 0) return;

    if (typeof f3 === 'undefined') {
        console.error("family-chart library not loaded!");
        return;
    }

    const mainId = rootPersonId || data[0].id;

    // Create the store
    const store = f3.createStore({
        data: data,
        main_id: mainId,
        node_separation: 250,
        level_separation: 150
    });

    // Setup SVG
    const width = container.clientWidth || 900;
    const height = Math.max(600, container.clientHeight || 700);
    container.innerHTML = '';

    // Create the SVG with Zoom handling using d3 and f3
    const svg = f3.createSvg(container);
    svg.style.backgroundColor = '#0f172a'; // slate-900
    svg.setAttribute('width', width);
    svg.setAttribute('height', height);

    // Setup custom Card display
    const Card = f3.elements.Card({
        svg: svg,
        store: store,
        card_dim: { w: 220, h: 70, text_x: 75, text_y: 15, img_w: 60, img_h: 60, img_x: 5, img_y: 5 },
        card_display: [
            (d) => `${d.data?.name || 'Unknown'}`,
            (d) => {
                let dateStr = "";
                const b = d.data?.birth_year;
                const dd = d.data?.death_year;
                if (b) dateStr += b;
                if (b && dd) dateStr += " – ";
                if (dd && !b) dateStr += "d. ";
                if (dd) dateStr += dd;
                return dateStr;
            }
        ],
        mini_tree: true,
        link_break: false
    });

    // Custom links style wrapper
    function customView(tree, svg, Card) {
        // Run standard f3 view
        f3.view(tree, svg, Card, {
            store: store,
            card_dim: { w: 220, h: 70, text_x: 75, text_y: 15, img_w: 60, img_h: 60, img_x: 5, img_y: 5 }
        });

        // Apply Editorial Archival colors to the generated SVG elements
        const d3svg = d3.select(svg);

        // Style nodes (cards)
        d3svg.selectAll('g.card rect')
            .attr('fill', '#1e293b') // slate-800
            .attr('stroke', '#334155') // slate-700
            .attr('stroke-width', 1)
            .attr('rx', 8)
            .attr('ry', 8);

        // Highlight root person
        d3svg.selectAll('g.card_cont')
            .filter(d => d && d.data && d.data.id === mainId)
            .select('rect')
            .attr('stroke', '#818cf8') // indigo-400
            .attr('stroke-width', 2.5);

        // Style the avatar fallback circles (if no image)
        d3svg.selectAll('g.card_cont').each(function (d) {
            if (!d || !d.data) return;
            const el = d3.select(this);
            const gender = d.data.data?.gender || 'U';
            const strokeColor = gender === 'M' ? '#3b82f6' : (gender === 'F' ? '#ec4899' : '#9ca3af');

            // Apply styles to the SVG icon container
            el.selectAll('.person-icon svg path').attr('fill', strokeColor).attr('opacity', 0.8);
        });

        // Style text tags specifically, removing HTML injection from standard tspan
        d3svg.selectAll('g.card text tspan:first-child')
            .attr('fill', '#e2e8f0')
            .attr('font-size', '14px')
            .attr('font-weight', '600')
            .attr('font-family', "'Playfair Display', serif")
            .attr('dy', '18'); // Explicit vertical offset for first text line

        d3svg.selectAll('g.card text tspan:nth-child(2)')
            .attr('fill', '#64748b')
            .attr('font-size', '11px')
            .attr('dy', '18'); // Stack beneath first line

        // Disable standard pointer events on background so text is selectable if needed
        d3svg.selectAll('g.card rect.card-bg').attr('pointer-events', 'none');

        // Style links (parent-child and spouse)
        d3svg.selectAll('path.link')
            .attr('stroke', '#d97706') // amber-600 for parent/child
            .attr('stroke-width', 2)
            .attr('opacity', 0.6)
            .attr('fill', 'none');

        // Note: f3 draws spouse links with class .link and .spouse sometimes, 
        // we could refine this further if needed.
    }

    // Initial render and zoom-to-fit
    store.setOnUpdate((props) => customView(store.getTree(), svg, Card));
    store.updateTree({ initial: true });
};
