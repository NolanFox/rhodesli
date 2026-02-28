/**
 * family-tree.js — Rhodesli heritage family tree.
 * AD-185: Card-based layout with T-shape connections.
 * Follows Ancestry/MyHeritage patterns: couples side-by-side,
 * vertical drop to children, expand arrows, circular portraits.
 * Research: docs/research/family-tree-ux-patterns.md
 */

(function() {
    "use strict";

    var svg, g, zoomBehavior;
    var allNodes = [];
    var currentPersonId = "";
    var showTheory = "true";

    // --- Card & layout constants ---
    var CARD_W = 180, CARD_H = 76;
    var PHOTO_R = 26;
    var V_GAP = 150;          // Vertical space between generation rows
    var H_GAP = 50;           // Between family groups in same row
    var COUPLE_GAP = 24;      // Between spouse cards (visible gold connector)
    var DROP_Y = 30;          // How far below couple the horizontal bar sits
    var EXPAND_R = 12;        // Expand arrow circle radius
    var COLORS = {
        cardBg: "#1e293b",
        cardBorder: "#334155",
        cardHover: "#253547",
        focalBorder: "#d4a574",
        nameText: "#e2e8f0",
        dateText: "#94a3b8",
        line: "#475569",
        coupleLine: "#d4a574",
        expandBg: "#4f46e5",
        expandHover: "#6366f1",
        photoBg: "#334155",
        photoInitial: "#64748b",
        svgBg: "#0f172a"
    };

    // --- Initialization ---
    window.initRhodesliTree = function(personId, theory) {
        currentPersonId = personId;
        showTheory = theory;
        setupSearch();
        setupPopupDismiss();
        loadTreeData(personId, 2);
    };

    // --- Data Loading ---
    function loadTreeData(personId, depth) {
        var loading = document.getElementById("tree-loading");
        if (loading) loading.style.display = "block";

        var url = "/api/tree/data?depth=" + (depth || 1) + "&show_theory=" + showTheory;
        if (personId) url += "&person_id=" + encodeURIComponent(personId);

        fetch(url)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (loading) loading.style.display = "none";
                if (!data.nodes || data.nodes.length === 0) {
                    var container = document.getElementById("tree-container");
                    if (container) container.innerHTML = '<p style="text-align:center;color:#94a3b8;padding:3rem 0">No family data found.</p>';
                    return;
                }
                currentPersonId = data.focal_person;
                allNodes = data.nodes;
                renderTree(currentPersonId);
            })
            .catch(function(err) {
                if (loading) loading.style.display = "none";
                console.error("Tree load failed:", err);
            });
    }

    function expandNode(personId, direction) {
        var url = "/api/tree/expand?person_id=" + encodeURIComponent(personId)
            + "&direction=" + direction + "&show_theory=" + showTheory;
        fetch(url)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (!data.nodes) return;
                mergeNodes(data.nodes);
                renderTree(currentPersonId);
            });
    }

    function mergeNodes(newNodes) {
        for (var i = 0; i < newNodes.length; i++) {
            var nn = newNodes[i];
            var existing = allNodes.find(function(n) { return n.id === nn.id; });
            if (!existing) {
                allNodes.push(nn);
            } else {
                if (nn.rels.father && !existing.rels.father) existing.rels.father = nn.rels.father;
                if (nn.rels.mother && !existing.rels.mother) existing.rels.mother = nn.rels.mother;
                ["spouses", "children"].forEach(function(key) {
                    if (nn.rels[key]) {
                        existing.rels[key] = existing.rels[key] || [];
                        nn.rels[key].forEach(function(id) {
                            if (existing.rels[key].indexOf(id) === -1) existing.rels[key].push(id);
                        });
                    }
                });
                existing.data["has_more_parents"] = nn.data["has_more_parents"];
                existing.data["has_more_children"] = nn.data["has_more_children"];
                existing.data["has_more_siblings"] = nn.data["has_more_siblings"];
            }
        }
    }

    // --- Build hierarchy from flat nodes ---
    function buildHierarchy(focalId) {
        var nodeMap = {};
        allNodes.forEach(function(n) { nodeMap[n.id] = n; });

        var visited = {};
        var queue = [{ id: focalId, gen: 0 }];
        visited[focalId] = 0;
        var generations = {};

        while (queue.length > 0) {
            var item = queue.shift();
            var node = nodeMap[item.id];
            if (!node) continue;

            var gen = item.gen;
            if (!generations[gen]) generations[gen] = [];
            generations[gen].push(node);

            [node.rels.father, node.rels.mother].forEach(function(pid) {
                if (pid && !visited.hasOwnProperty(pid)) {
                    visited[pid] = gen - 1;
                    queue.push({ id: pid, gen: gen - 1 });
                }
            });
            (node.rels.children || []).forEach(function(cid) {
                if (!visited.hasOwnProperty(cid)) {
                    visited[cid] = gen + 1;
                    queue.push({ id: cid, gen: gen + 1 });
                }
            });
            (node.rels.spouses || []).forEach(function(sid) {
                if (!visited.hasOwnProperty(sid)) {
                    visited[sid] = gen;
                    queue.push({ id: sid, gen: gen });
                }
            });
        }
        return { generations: generations, genOf: visited, nodeMap: nodeMap };
    }

    // --- Layout: assign x,y; build connections ---
    function layoutNodes(focalId) {
        var h = buildHierarchy(focalId);
        var gens = h.generations;
        var genOf = h.genOf;
        var nodeMap = h.nodeMap;
        var genKeys = Object.keys(gens).map(Number).sort(function(a, b) { return a - b; });

        var positions = {};
        var couples = [];   // { ids: [a,b], midX, y }
        var connections = []; // { type, ... }

        // Layout each generation row
        genKeys.forEach(function(gk) {
            var people = gens[gk];
            var placed = {};
            var groups = []; // each group = [person, ...spouses]

            people.forEach(function(p) {
                if (placed[p.id]) return;
                var group = [p];
                placed[p.id] = true;
                (p.rels.spouses || []).forEach(function(sid) {
                    var sp = nodeMap[sid];
                    if (sp && !placed[sid] && genOf[sid] === gk) {
                        group.push(sp);
                        placed[sid] = true;
                    }
                });
                groups.push(group);
            });

            // Calculate total width
            var totalWidth = 0;
            groups.forEach(function(grp, i) {
                totalWidth += grp.length * CARD_W + (grp.length - 1) * COUPLE_GAP;
                if (i > 0) totalWidth += H_GAP;
            });

            var x = -totalWidth / 2;
            var y = gk * V_GAP;

            groups.forEach(function(grp, gi) {
                if (gi > 0) x += H_GAP;
                var groupStartX = x;
                grp.forEach(function(person, pi) {
                    if (pi > 0) x += COUPLE_GAP;
                    positions[person.id] = { x: x, y: y, node: person };
                    x += CARD_W;
                });
                var groupEndX = x;

                // Record couple for connection drawing
                if (grp.length >= 2) {
                    var ids = grp.map(function(p) { return p.id; });
                    couples.push({
                        ids: ids,
                        midX: (groupStartX + groupEndX) / 2,
                        y: y
                    });
                    // Draw couple connector line
                    for (var ci = 0; ci < grp.length - 1; ci++) {
                        var leftPos = positions[grp[ci].id];
                        var rightPos = positions[grp[ci + 1].id];
                        connections.push({
                            type: "couple",
                            x1: leftPos.x + CARD_W,
                            y1: leftPos.y + CARD_H / 2,
                            x2: rightPos.x,
                            y2: rightPos.y + CARD_H / 2
                        });
                    }
                }
            });
        });

        // Build parent-child T-shape connections
        allNodes.forEach(function(n) {
            var children = n.rels.children || [];
            if (children.length === 0) return;
            var nPos = positions[n.id];
            if (!nPos) return;

            // Find this person's spouse(s) to form couple midpoint
            var spouses = (n.rels.spouses || []).filter(function(s) { return positions[s]; });
            // Only draw from one parent per couple (avoid double-drawing)
            if (spouses.length > 0) {
                var firstSpouse = spouses[0];
                if (n.id > firstSpouse && positions[firstSpouse]) return; // let the lower-id parent draw
            }

            // Calculate parent anchor point (midpoint of couple, or center of single parent)
            var parentX, parentY;
            if (spouses.length > 0 && positions[spouses[0]]) {
                var sp = positions[spouses[0]];
                parentX = (nPos.x + CARD_W / 2 + sp.x + CARD_W / 2) / 2;
                parentY = nPos.y + CARD_H;
            } else {
                parentX = nPos.x + CARD_W / 2;
                parentY = nPos.y + CARD_H;
            }

            // Collect child positions
            var childPositions = [];
            children.forEach(function(cid) {
                var cp = positions[cid];
                if (cp) childPositions.push({ x: cp.x + CARD_W / 2, y: cp.y });
            });
            if (childPositions.length === 0) return;

            // T-shape: vertical drop from parent, horizontal bar, vertical to each child
            var barY = parentY + DROP_Y;
            connections.push({ type: "drop", x: parentX, y1: parentY, y2: barY });

            var minCX = Math.min.apply(null, childPositions.map(function(c) { return c.x; }));
            var maxCX = Math.max.apply(null, childPositions.map(function(c) { return c.x; }));
            // Horizontal bar spans from leftmost child to rightmost child
            if (childPositions.length > 1) {
                connections.push({ type: "bar", y: barY, x1: minCX, x2: maxCX });
            }
            // Also connect parent drop to bar if parent midpoint is outside child range
            if (parentX < minCX || parentX > maxCX) {
                connections.push({ type: "bar", y: barY, x1: Math.min(parentX, minCX), x2: Math.max(parentX, maxCX) });
            }

            // Vertical from bar to each child
            childPositions.forEach(function(cp) {
                connections.push({ type: "childDrop", x: cp.x, y1: barY, y2: cp.y });
            });
        });

        return { positions: positions, connections: connections, couples: couples };
    }

    // --- Render ---
    function renderTree(focalId) {
        if (!allNodes || allNodes.length === 0) return;

        var container = document.getElementById("tree-container");
        if (!container) return;

        var layout = layoutNodes(focalId);
        var positions = layout.positions;
        var connections = layout.connections;

        // Create or reuse SVG
        if (!svg) {
            container.innerHTML = "";
            var w = container.clientWidth;
            var h = container.clientHeight;

            svg = d3.select(container).append("svg")
                .attr("width", w).attr("height", h)
                .style("background", COLORS.svgBg);

            g = svg.append("g");

            zoomBehavior = d3.zoom()
                .scaleExtent([0.15, 3])
                .on("zoom", function(event) { g.attr("transform", event.transform); });
            svg.call(zoomBehavior);

            window.addEventListener("resize", function() {
                svg.attr("width", container.clientWidth).attr("height", container.clientHeight);
            });
        }

        g.selectAll("*").remove();
        var defs = g.append("defs");

        // Clip paths for circular photos
        Object.keys(positions).forEach(function(pid) {
            defs.append("clipPath")
                .attr("id", "clip-" + pid.replace(/[^a-zA-Z0-9]/g, "_"))
                .append("circle").attr("cx", 12 + PHOTO_R).attr("cy", CARD_H / 2).attr("r", PHOTO_R);
        });

        // --- Draw connections ---
        var lineGroup = g.append("g").attr("class", "connections");

        connections.forEach(function(c) {
            if (c.type === "couple") {
                lineGroup.append("line")
                    .attr("x1", c.x1).attr("y1", c.y1)
                    .attr("x2", c.x2).attr("y2", c.y2)
                    .attr("stroke", COLORS.coupleLine).attr("stroke-width", 2);
            } else if (c.type === "drop" || c.type === "childDrop") {
                lineGroup.append("line")
                    .attr("x1", c.x).attr("y1", c.y1)
                    .attr("x2", c.x).attr("y2", c.y2)
                    .attr("stroke", COLORS.line).attr("stroke-width", 1.5);
            } else if (c.type === "bar") {
                lineGroup.append("line")
                    .attr("x1", c.x1).attr("y1", c.y)
                    .attr("x2", c.x2).attr("y2", c.y)
                    .attr("stroke", COLORS.line).attr("stroke-width", 1.5);
            }
        });

        // --- Draw person cards ---
        var nodeData = Object.keys(positions).map(function(pid) {
            return { id: pid, x: positions[pid].x, y: positions[pid].y, node: positions[pid].node };
        });

        var nodeGroup = g.append("g").attr("class", "nodes");
        var cards = nodeGroup.selectAll(".person-node")
            .data(nodeData, function(d) { return d.id; })
            .enter().append("g")
            .attr("class", "person-node")
            .attr("transform", function(d) { return "translate(" + d.x + "," + d.y + ")"; })
            .style("cursor", "pointer")
            .on("click", function(event, d) {
                event.stopPropagation();
                showNodePopup(event, d.node.data, d.id);
            });

        // Card background
        cards.append("rect")
            .attr("width", CARD_W).attr("height", CARD_H)
            .attr("rx", 10).attr("ry", 10)
            .attr("fill", COLORS.cardBg)
            .attr("stroke", function(d) { return d.id === focalId ? COLORS.focalBorder : COLORS.cardBorder; })
            .attr("stroke-width", function(d) { return d.id === focalId ? 2.5 : 1; });

        // Circular photo
        cards.each(function(d) {
            var el = d3.select(this);
            var cx = 12 + PHOTO_R, cy = CARD_H / 2;
            var clipId = "clip-" + d.id.replace(/[^a-zA-Z0-9]/g, "_");
            var photoUrl = d.node.data.avatar || d.node.data.photo_url;

            if (photoUrl) {
                el.append("image")
                    .attr("x", 12).attr("y", cy - PHOTO_R)
                    .attr("width", PHOTO_R * 2).attr("height", PHOTO_R * 2)
                    .attr("href", photoUrl)
                    .attr("clip-path", "url(#" + clipId + ")")
                    .attr("preserveAspectRatio", "xMidYMid slice");
            } else {
                el.append("circle").attr("cx", cx).attr("cy", cy).attr("r", PHOTO_R)
                    .attr("fill", COLORS.photoBg);
                el.append("text").attr("x", cx).attr("y", cy)
                    .attr("text-anchor", "middle").attr("dy", "0.35em")
                    .attr("fill", COLORS.photoInitial)
                    .attr("font-size", PHOTO_R + "px")
                    .attr("font-family", "'Georgia', serif")
                    .text((d.node.data["first name"] || "?")[0].toUpperCase());
            }

            // Photo border ring
            el.append("circle").attr("cx", cx).attr("cy", cy).attr("r", PHOTO_R)
                .attr("fill", "none").attr("stroke", COLORS.cardBorder).attr("stroke-width", 1);
        });

        // Name text
        cards.append("text")
            .attr("x", 12 + PHOTO_R * 2 + 10).attr("y", CARD_H / 2 - 6)
            .attr("fill", COLORS.nameText)
            .attr("font-size", "12px").attr("font-weight", "600")
            .attr("font-family", "'Georgia', serif")
            .text(function(d) {
                var name = ((d.node.data["first name"] || "") + " " + (d.node.data["last name"] || "")).trim();
                return name.length > 20 ? name.substring(0, 18) + "\u2026" : name;
            });

        // Lifespan text
        cards.append("text")
            .attr("x", 12 + PHOTO_R * 2 + 10).attr("y", CARD_H / 2 + 10)
            .attr("fill", COLORS.dateText).attr("font-size", "10px")
            .text(function(d) { return d.node.data.lifespan || ""; });

        // --- Expand arrows ---
        var arrowGroup = g.append("g").attr("class", "expand-arrows");

        nodeData.forEach(function(d) {
            var data = d.node.data;
            var cx = d.x + CARD_W / 2;

            if (data["has_more_parents"]) {
                drawExpandArrow(arrowGroup, cx, d.y - 18, "up", d.id, "parents");
            }
            if (data["has_more_children"]) {
                drawExpandArrow(arrowGroup, cx, d.y + CARD_H + 18, "down", d.id, "children");
            }
            if (data["has_more_siblings"]) {
                drawExpandArrow(arrowGroup, d.x - 18, d.y + CARD_H / 2, "left", d.id, "siblings");
            }
        });

        fitToContent();
    }

    function drawExpandArrow(parent, cx, cy, direction, personId, expandDir) {
        var grp = parent.append("g")
            .attr("class", "expand-btn")
            .attr("transform", "translate(" + cx + "," + cy + ")")
            .style("cursor", "pointer")
            .on("click", function(event) {
                event.stopPropagation();
                expandNode(personId, expandDir);
            });

        grp.append("circle").attr("r", EXPAND_R)
            .attr("fill", COLORS.expandBg).attr("stroke", COLORS.svgBg).attr("stroke-width", 2);

        // Arrow glyph
        var arrow;
        if (direction === "up") arrow = "M-4,2 L0,-4 L4,2";
        else if (direction === "down") arrow = "M-4,-2 L0,4 L4,-2";
        else if (direction === "left") arrow = "M2,-4 L-4,0 L2,4";
        else arrow = "M-2,-4 L4,0 L-2,4";

        grp.append("path").attr("d", arrow)
            .attr("fill", "white").attr("stroke", "none");
    }

    function fitToContent() {
        if (!g || !svg) return;
        var bbox = g.node().getBBox();
        if (bbox.width === 0 || bbox.height === 0) return;

        var container = document.getElementById("tree-container");
        var w = container.clientWidth, h = container.clientHeight;
        var pad = 60;

        var scaleX = (w - pad * 2) / bbox.width;
        var scaleY = (h - pad * 2) / bbox.height;
        var scale = Math.min(scaleX, scaleY, 1.2);

        var tx = w / 2 - (bbox.x + bbox.width / 2) * scale;
        var ty = h / 2 - (bbox.y + bbox.height / 2) * scale;

        svg.transition().duration(600).call(
            zoomBehavior.transform,
            d3.zoomIdentity.translate(tx, ty).scale(scale)
        );
    }

    // --- Node Action Popup ---
    function showNodePopup(event, nodeData, nodeId) {
        var popup = document.getElementById("tree-node-popup");
        if (!popup) return;

        var name = ((nodeData["first name"] || "") + " " + (nodeData["last name"] || "")).trim();
        var html = '<div style="font-weight:600;padding:8px 14px;color:#e2e8f0;font-size:14px;border-bottom:1px solid #334155;margin-bottom:4px;font-family:Georgia,serif">' + name + '</div>';

        if (nodeData.identity_url)
            html += '<a href="' + nodeData.identity_url + '">View Profile</a>';
        html += '<button data-action="tree-focus" data-person-id="' + nodeId + '">Focus Tree Here</button>';
        if (nodeData["has_more_parents"])
            html += '<button data-action="tree-expand" data-person-id="' + nodeId + '" data-direction="parents">Expand Parents</button>';
        if (nodeData["has_more_children"])
            html += '<button data-action="tree-expand" data-person-id="' + nodeId + '" data-direction="children">Expand Children</button>';
        if (nodeData["has_more_siblings"])
            html += '<button data-action="tree-expand" data-person-id="' + nodeId + '" data-direction="siblings">Expand Siblings</button>';

        popup.innerHTML = html;
        popup.classList.remove("hidden");

        var x = event.clientX + 12, y = event.clientY + 12;
        if (x + 200 > window.innerWidth) x = window.innerWidth - 210;
        if (y + 220 > window.innerHeight) y = window.innerHeight - 230;
        popup.style.left = x + "px";
        popup.style.top = y + "px";
        popup.style.position = "fixed";
    }

    function hideNodePopup() {
        var popup = document.getElementById("tree-node-popup");
        if (popup) popup.classList.add("hidden");
    }

    function setupPopupDismiss() {
        document.addEventListener("click", function(e) {
            var popup = document.getElementById("tree-node-popup");
            if (popup && !popup.contains(e.target) && !e.target.closest(".person-node")) {
                hideNodePopup();
            }
        });

        document.addEventListener("click", function(e) {
            var btn = e.target.closest("[data-action]");
            if (!btn) return;
            var action = btn.getAttribute("data-action");
            var personId = btn.getAttribute("data-person-id");

            if (action === "tree-focus" && personId) {
                hideNodePopup();
                loadTreeData(personId, 2);
            } else if (action === "tree-expand" && personId) {
                hideNodePopup();
                expandNode(personId, btn.getAttribute("data-direction"));
            } else if (action === "tree-zoom-in") {
                if (svg && zoomBehavior) svg.transition().duration(300).call(zoomBehavior.scaleBy, 1.4);
            } else if (action === "tree-zoom-out") {
                if (svg && zoomBehavior) svg.transition().duration(300).call(zoomBehavior.scaleBy, 0.7);
            } else if (action === "tree-fit") {
                fitToContent();
            }
        });
    }

    // --- Search ---
    var searchTimeout = null;

    function setupSearch() {
        var input = document.getElementById("tree-search-input");
        var results = document.getElementById("tree-search-results");
        if (!input || !results) return;

        input.addEventListener("input", function() {
            clearTimeout(searchTimeout);
            var q = input.value.trim();
            if (q.length < 2) { results.classList.add("hidden"); results.innerHTML = ""; return; }
            searchTimeout = setTimeout(function() {
                fetch("/api/tree/search?q=" + encodeURIComponent(q))
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        if (!data.results || data.results.length === 0) {
                            results.innerHTML = '<div class="result-item"><span class="badge">No results</span></div>';
                            results.classList.remove("hidden");
                            return;
                        }
                        var html = "";
                        data.results.forEach(function(r) {
                            var badge = r.has_photo ? "Archive" : "GEDCOM";
                            html += '<div class="result-item" data-person-id="' + r.id + '">'
                                + '<span class="name">' + r.name + '</span> '
                                + '<span class="badge">(' + badge + ')</span></div>';
                        });
                        results.innerHTML = html;
                        results.classList.remove("hidden");
                    });
            }, 250);
        });

        results.addEventListener("click", function(e) {
            var item = e.target.closest(".result-item");
            if (!item) return;
            var pid = item.getAttribute("data-person-id");
            if (pid) {
                input.value = item.querySelector(".name").textContent;
                results.classList.add("hidden");
                loadTreeData(pid, 2);
                window.history.pushState({}, "", "/tree?person=" + encodeURIComponent(pid));
            }
        });

        input.addEventListener("blur", function() {
            setTimeout(function() { results.classList.add("hidden"); }, 200);
        });
        input.addEventListener("focus", function() {
            if (results.innerHTML && input.value.trim().length >= 2) results.classList.remove("hidden");
        });
    }

    // --- Theory Toggle ---
    document.addEventListener("change", function(e) {
        if (e.target && e.target.id === "tree-show-theory") {
            showTheory = e.target.checked ? "true" : "false";
            loadTreeData(currentPersonId, 2);
        }
    });

})();
