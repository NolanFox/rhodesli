/**
 * family-tree.js — Rhodesli heritage family tree.
 * AD-185: Card-based layout with T-shape connections.
 * AD-186: Portrait cards with photo-dominant design.
 * Faces are the hero element — 50% of card area.
 * Gender-coded rings, glassmorphic cards, hover micro-interactions.
 */

(function() {
    "use strict";

    var svg, g, zoomBehavior;
    var allNodes = [];
    var currentPersonId = "";
    var showTheory = "true";
    var baseNodeIds = {};
    var expandedDirs = {};

    // --- Portrait card constants (photo-dominant) ---
    var CARD_W = 156, CARD_H = 196;
    var PHOTO_R = 40;                      // 80px diameter — hero element
    var PHOTO_CX = CARD_W / 2;            // Centered horizontally
    var PHOTO_CY = 16 + PHOTO_R;          // 16px top padding + radius = 56
    var NAME_Y1 = PHOTO_CY + PHOTO_R + 20; // First name baseline
    var NAME_Y2 = NAME_Y1 + 17;            // Last name baseline
    var DATE_Y  = NAME_Y2 + 15;            // Lifespan baseline
    var CARD_RX = 14;

    var V_GAP = 260;
    var H_GAP = 36;
    var COUPLE_GAP = 20;
    var DROP_Y = 36;
    var EXPAND_R = 13;

    var COLORS = {
        svgBg:        "#0b1120",
        cardBg:       "#151d2e",
        cardBorder:   "rgba(148, 163, 184, 0.10)",
        cardHover:    "#1c2740",
        focalBorder:  "#d4a574",
        focalGlow:    "rgba(212, 165, 116, 0.25)",
        nameText:     "#f1f5f9",
        dateText:     "#8b9ab5",
        line:         "rgba(71, 85, 105, 0.5)",
        coupleLine:   "rgba(212, 165, 116, 0.6)",
        coupleDot:    "#d4a574",
        expandBg:     "#4f46e5",
        collapseBg:   "#7c3aed",
        photoBg:      "#1a2336",
        photoInitial: "#4b5e7a",
        genderM:      "#60a5fa",
        genderF:      "#f9a8d4",
        genderU:      "#64748b"
    };

    // --- Initialization ---
    window.initRhodesliTree = function(personId, theory) {
        currentPersonId = personId;
        showTheory = theory;
        setupSearch();
        setupPopupDismiss();
        setupKeyboard();
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
                    if (container) container.innerHTML = '<p style="text-align:center;color:#8b9ab5;padding:3rem 0;font-family:Georgia,serif;font-size:15px">No family data found.</p>';
                    return;
                }
                currentPersonId = data.focal_person;
                allNodes = data.nodes;
                baseNodeIds = {};
                expandedDirs = {};
                allNodes.forEach(function(n) { baseNodeIds[n.id] = true; });
                renderTree(currentPersonId);
            })
            .catch(function(err) {
                if (loading) loading.style.display = "none";
                console.error("Tree load failed:", err);
            });
    }

    function expandNode(personId, direction) {
        var key = personId + "|" + direction;
        var url = "/api/tree/expand?person_id=" + encodeURIComponent(personId)
            + "&direction=" + direction + "&show_theory=" + showTheory;
        fetch(url)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (!data.nodes) return;
                var existingIds = {};
                allNodes.forEach(function(n) { existingIds[n.id] = true; });
                mergeNodes(data.nodes);
                var addedIds = [];
                data.nodes.forEach(function(n) {
                    if (!existingIds[n.id]) addedIds.push(n.id);
                });
                expandedDirs[key] = addedIds;
                renderTree(currentPersonId);
            });
    }

    function collapseNode(personId, direction) {
        var key = personId + "|" + direction;
        delete expandedDirs[key];
        var keepIds = {};
        Object.keys(baseNodeIds).forEach(function(id) { keepIds[id] = true; });
        Object.keys(expandedDirs).forEach(function(k) {
            expandedDirs[k].forEach(function(id) { keepIds[id] = true; });
        });
        allNodes = allNodes.filter(function(n) { return keepIds[n.id]; });
        renderTree(currentPersonId);
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
        var couples = [];
        var connections = [];

        genKeys.forEach(function(gk) {
            var people = gens[gk];
            var placed = {};
            var groups = [];
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

                if (grp.length >= 2) {
                    var ids = grp.map(function(p) { return p.id; });
                    couples.push({ ids: ids, midX: (groupStartX + groupEndX) / 2, y: y });
                    for (var ci = 0; ci < grp.length - 1; ci++) {
                        var leftPos = positions[grp[ci].id];
                        var rightPos = positions[grp[ci + 1].id];
                        connections.push({
                            type: "couple",
                            x1: leftPos.x + CARD_W,
                            y1: leftPos.y + PHOTO_CY,
                            x2: rightPos.x,
                            y2: rightPos.y + PHOTO_CY,
                            midX: (leftPos.x + CARD_W + rightPos.x) / 2
                        });
                    }
                }
            });
        });

        // Parent-child T-shape connections
        allNodes.forEach(function(n) {
            var children = n.rels.children || [];
            if (children.length === 0) return;
            var nPos = positions[n.id];
            if (!nPos) return;

            var spouses = (n.rels.spouses || []).filter(function(s) { return positions[s]; });
            if (spouses.length > 0) {
                var firstSpouse = spouses[0];
                if (n.id > firstSpouse && positions[firstSpouse]) return;
            }

            var parentX, parentY;
            if (spouses.length > 0 && positions[spouses[0]]) {
                var sp = positions[spouses[0]];
                parentX = (nPos.x + CARD_W / 2 + sp.x + CARD_W / 2) / 2;
                parentY = nPos.y + CARD_H;
            } else {
                parentX = nPos.x + CARD_W / 2;
                parentY = nPos.y + CARD_H;
            }

            var childPositions = [];
            children.forEach(function(cid) {
                var cp = positions[cid];
                if (cp) childPositions.push({ x: cp.x + CARD_W / 2, y: cp.y });
            });
            if (childPositions.length === 0) return;

            var barY = parentY + DROP_Y;
            connections.push({ type: "drop", x: parentX, y1: parentY, y2: barY });

            var minCX = Math.min.apply(null, childPositions.map(function(c) { return c.x; }));
            var maxCX = Math.max.apply(null, childPositions.map(function(c) { return c.x; }));
            if (childPositions.length > 1) {
                connections.push({ type: "bar", y: barY, x1: minCX, x2: maxCX });
            }
            if (parentX < minCX || parentX > maxCX) {
                connections.push({ type: "bar", y: barY, x1: Math.min(parentX, minCX), x2: Math.max(parentX, maxCX) });
            }
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

        if (!svg) {
            container.innerHTML = "";
            var w = container.clientWidth;
            var hh = container.clientHeight;
            svg = d3.select(container).append("svg")
                .attr("width", w).attr("height", hh)
                .style("background", COLORS.svgBg);
            g = svg.append("g");
            zoomBehavior = d3.zoom()
                .scaleExtent([0.1, 3])
                .on("zoom", function(event) {
                    g.attr("transform", event.transform);
                    // Progressive detail: hide dates at low zoom
                    var k = event.transform.k;
                    g.selectAll(".date-label").attr("opacity", k > 0.35 ? 1 : 0);
                    g.selectAll(".name-label").attr("opacity", k > 0.25 ? 1 : 0);
                });
            svg.call(zoomBehavior);
            window.addEventListener("resize", function() {
                svg.attr("width", container.clientWidth).attr("height", container.clientHeight);
            });
        }

        g.selectAll("*").remove();
        var defs = g.append("defs");

        // Glow filter for focal person
        var glow = defs.append("filter").attr("id", "focalGlow")
            .attr("x", "-50%").attr("y", "-50%").attr("width", "200%").attr("height", "200%");
        glow.append("feGaussianBlur").attr("stdDeviation", "6").attr("result", "blur");
        var glowMerge = glow.append("feMerge");
        glowMerge.append("feMergeNode").attr("in", "blur");
        glowMerge.append("feMergeNode").attr("in", "SourceGraphic");

        // Hover shadow filter
        var shadow = defs.append("filter").attr("id", "hoverShadow")
            .attr("x", "-15%").attr("y", "-15%").attr("width", "140%").attr("height", "150%");
        shadow.append("feDropShadow").attr("dx", "0").attr("dy", "6").attr("stdDeviation", "10")
            .attr("flood-color", "rgba(0,0,0,0.45)").attr("flood-opacity", "0.45");

        // Clip paths for circular photos (centered in portrait card)
        Object.keys(positions).forEach(function(pid) {
            defs.append("clipPath")
                .attr("id", "clip-" + pid.replace(/[^a-zA-Z0-9]/g, "_"))
                .append("circle").attr("cx", PHOTO_CX).attr("cy", PHOTO_CY).attr("r", PHOTO_R);
        });

        // --- Draw connections ---
        var lineGroup = g.append("g").attr("class", "connections");
        connections.forEach(function(c) {
            if (c.type === "couple") {
                // Dashed gold line with center dot
                lineGroup.append("line")
                    .attr("x1", c.x1).attr("y1", c.y1).attr("x2", c.x2).attr("y2", c.y2)
                    .attr("stroke", COLORS.coupleLine).attr("stroke-width", 2)
                    .attr("stroke-dasharray", "6,4");
                lineGroup.append("circle")
                    .attr("cx", c.midX).attr("cy", c.y1).attr("r", 3.5)
                    .attr("fill", COLORS.coupleDot);
            } else if (c.type === "drop" || c.type === "childDrop") {
                lineGroup.append("line")
                    .attr("x1", c.x).attr("y1", c.y1).attr("x2", c.x).attr("y2", c.y2)
                    .attr("stroke", COLORS.line).attr("stroke-width", 1.5);
            } else if (c.type === "bar") {
                lineGroup.append("line")
                    .attr("x1", c.x1).attr("y1", c.y).attr("x2", c.x2).attr("y2", c.y)
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

        // Hover micro-interactions
        cards.on("mouseenter", function() {
                var card = d3.select(this);
                card.select(".card-bg").transition().duration(180)
                    .attr("fill", COLORS.cardHover)
                    .attr("filter", "url(#hoverShadow)");
                card.select(".photo-ring").transition().duration(180)
                    .attr("stroke-width", 3.5);
                card.transition().duration(180)
                    .attr("transform", function(d) {
                        return "translate(" + d.x + "," + (d.y - 3) + ")";
                    });
            })
            .on("mouseleave", function() {
                var card = d3.select(this);
                card.select(".card-bg").transition().duration(250)
                    .attr("fill", COLORS.cardBg)
                    .attr("filter", null);
                card.select(".photo-ring").transition().duration(250)
                    .attr("stroke-width", 2.5);
                card.transition().duration(250)
                    .attr("transform", function(d) {
                        return "translate(" + d.x + "," + d.y + ")";
                    });
            });

        // Card background — rounded rect
        cards.append("rect")
            .attr("class", "card-bg")
            .attr("width", CARD_W).attr("height", CARD_H)
            .attr("rx", CARD_RX).attr("ry", CARD_RX)
            .attr("fill", COLORS.cardBg)
            .attr("stroke", function(d) { return d.id === focalId ? COLORS.focalBorder : COLORS.cardBorder; })
            .attr("stroke-width", function(d) { return d.id === focalId ? 2 : 1; });

        // Focal person outer glow ring
        cards.each(function(d) {
            if (d.id === focalId) {
                d3.select(this).insert("circle", ":first-child")
                    .attr("cx", PHOTO_CX).attr("cy", PHOTO_CY)
                    .attr("r", PHOTO_R + 8)
                    .attr("fill", "none").attr("stroke", COLORS.focalGlow)
                    .attr("stroke-width", 4)
                    .attr("filter", "url(#focalGlow)");
            }
        });

        // Circular photo — hero element, top-centered
        cards.each(function(d) {
            var el = d3.select(this);
            var clipId = "clip-" + d.id.replace(/[^a-zA-Z0-9]/g, "_");
            var photoUrl = d.node.data.avatar || d.node.data.photo_url;

            if (photoUrl) {
                el.append("image")
                    .attr("x", PHOTO_CX - PHOTO_R).attr("y", PHOTO_CY - PHOTO_R)
                    .attr("width", PHOTO_R * 2).attr("height", PHOTO_R * 2)
                    .attr("href", photoUrl)
                    .attr("clip-path", "url(#" + clipId + ")")
                    .attr("preserveAspectRatio", "xMidYMid slice");
            } else {
                // Placeholder: dark circle with initial
                el.append("circle").attr("cx", PHOTO_CX).attr("cy", PHOTO_CY).attr("r", PHOTO_R)
                    .attr("fill", COLORS.photoBg);
                el.append("text").attr("x", PHOTO_CX).attr("y", PHOTO_CY)
                    .attr("text-anchor", "middle").attr("dy", "0.35em")
                    .attr("fill", COLORS.photoInitial)
                    .attr("font-size", "28px")
                    .attr("font-family", "'Georgia', serif")
                    .text((d.node.data["first name"] || "?")[0].toUpperCase());
            }

            // Gender-coded photo ring
            var gender = d.node.data.gender || "U";
            var ringColor = gender === "M" ? COLORS.genderM : gender === "F" ? COLORS.genderF : COLORS.genderU;
            el.append("circle")
                .attr("class", "photo-ring")
                .attr("cx", PHOTO_CX).attr("cy", PHOTO_CY).attr("r", PHOTO_R)
                .attr("fill", "none").attr("stroke", ringColor).attr("stroke-width", 2.5);
        });

        // First name — centered below photo
        cards.append("text")
            .attr("class", "name-label")
            .attr("x", CARD_W / 2).attr("y", NAME_Y1)
            .attr("text-anchor", "middle")
            .attr("fill", COLORS.nameText)
            .attr("font-size", "13px").attr("font-weight", "600")
            .attr("font-family", "'Inter', system-ui, -apple-system, sans-serif")
            .text(function(d) {
                var first = d.node.data["first name"] || "";
                return first.length > 16 ? first.substring(0, 14) + "\u2026" : first;
            });

        // Last name — centered, slightly lighter
        cards.append("text")
            .attr("class", "name-label")
            .attr("x", CARD_W / 2).attr("y", NAME_Y2)
            .attr("text-anchor", "middle")
            .attr("fill", COLORS.nameText)
            .attr("font-size", "12px").attr("font-weight", "500")
            .attr("font-family", "'Inter', system-ui, -apple-system, sans-serif")
            .text(function(d) {
                var last = d.node.data["last name"] || "";
                return last.length > 16 ? last.substring(0, 14) + "\u2026" : last;
            });

        // Lifespan — subtle, centered
        cards.append("text")
            .attr("class", "date-label")
            .attr("x", CARD_W / 2).attr("y", DATE_Y)
            .attr("text-anchor", "middle")
            .attr("fill", COLORS.dateText).attr("font-size", "10.5px")
            .attr("font-family", "'Inter', system-ui, -apple-system, sans-serif")
            .attr("letter-spacing", "0.03em")
            .text(function(d) { return d.node.data.lifespan || ""; });

        // --- Expand/collapse arrows ---
        var arrowGroup = g.append("g").attr("class", "expand-arrows");
        nodeData.forEach(function(d) {
            var data = d.node.data;
            var cx = d.x + CARD_W / 2;
            var dirs = [
                { flag: "has_more_parents", dir: "parents", arrowDir: "up", ax: cx, ay: d.y - 20 },
                { flag: "has_more_children", dir: "children", arrowDir: "down", ax: cx, ay: d.y + CARD_H + 20 },
                { flag: "has_more_siblings", dir: "siblings", arrowDir: "left", ax: d.x - 20, ay: d.y + CARD_H / 2 }
            ];
            dirs.forEach(function(dd) {
                var key = d.id + "|" + dd.dir;
                var isExpanded = expandedDirs.hasOwnProperty(key);
                if (data[dd.flag] || isExpanded) {
                    drawExpandArrow(arrowGroup, dd.ax, dd.ay, dd.arrowDir, d.id, dd.dir, isExpanded);
                }
            });
        });

        fitToContent();
    }

    function drawExpandArrow(parent, cx, cy, direction, personId, expandDir, isCollapse) {
        var grp = parent.append("g")
            .attr("class", "expand-btn")
            .attr("transform", "translate(" + cx + "," + cy + ")")
            .style("cursor", "pointer")
            .on("click", function(event) {
                event.stopPropagation();
                if (isCollapse) {
                    collapseNode(personId, expandDir);
                } else {
                    expandNode(personId, expandDir);
                }
            });

        grp.append("circle").attr("r", EXPAND_R)
            .attr("fill", isCollapse ? COLORS.collapseBg : COLORS.expandBg)
            .attr("stroke", COLORS.svgBg).attr("stroke-width", 2);

        if (isCollapse) {
            grp.append("line").attr("x1", -4).attr("y1", 0).attr("x2", 4).attr("y2", 0)
                .attr("stroke", "white").attr("stroke-width", 2).attr("stroke-linecap", "round");
        } else {
            var arrow;
            if (direction === "up") arrow = "M-4,2 L0,-4 L4,2";
            else if (direction === "down") arrow = "M-4,-2 L0,4 L4,-2";
            else if (direction === "left") arrow = "M2,-4 L-4,0 L2,4";
            else arrow = "M-2,-4 L4,0 L-2,4";
            grp.append("path").attr("d", arrow).attr("fill", "white").attr("stroke", "none");
        }

        // Hover effect on expand buttons
        grp.on("mouseenter", function() {
            d3.select(this).select("circle").transition().duration(150)
                .attr("r", EXPAND_R + 2);
        }).on("mouseleave", function() {
            d3.select(this).select("circle").transition().duration(200)
                .attr("r", EXPAND_R);
        });
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
        var scale = Math.min(scaleX, scaleY, 1.0);
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
        var photoUrl = nodeData.avatar || nodeData.photo_url || "";
        var gender = nodeData.gender || "U";
        var ringColor = gender === "M" ? COLORS.genderM : gender === "F" ? COLORS.genderF : COLORS.genderU;

        var html = '<div style="display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid #1e293b;margin-bottom:4px">';
        if (photoUrl) {
            html += '<img src="' + photoUrl + '" style="width:40px;height:40px;border-radius:50%;object-fit:cover;border:2px solid ' + ringColor + '" />';
        } else {
            html += '<div style="width:40px;height:40px;border-radius:50%;background:#1a2336;border:2px solid ' + ringColor + ';display:flex;align-items:center;justify-content:center;color:#4b5e7a;font-family:Georgia,serif;font-size:18px">' + (name[0] || "?").toUpperCase() + '</div>';
        }
        html += '<span style="font-weight:600;color:#f1f5f9;font-size:14px;font-family:Georgia,serif">' + name + '</span></div>';

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
        if (x + 220 > window.innerWidth) x = window.innerWidth - 230;
        if (y + 260 > window.innerHeight) y = window.innerHeight - 270;
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

    // --- Keyboard shortcuts ---
    function setupKeyboard() {
        document.addEventListener("keydown", function(e) {
            if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
            if ((e.key === "+" || e.key === "=") && svg && zoomBehavior) {
                e.preventDefault();
                svg.transition().duration(200).call(zoomBehavior.scaleBy, 1.3);
            } else if (e.key === "-" && svg && zoomBehavior) {
                e.preventDefault();
                svg.transition().duration(200).call(zoomBehavior.scaleBy, 0.7);
            } else if (e.key === "0" && svg) {
                e.preventDefault();
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
