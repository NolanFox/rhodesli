/**
 * family-tree.js — Rhodesli heritage family tree.
 * DD-004: Floating-face design — faces ARE the tree.
 * DD-005: Professional timeline slider + fluid card animations.
 * Photo-dominant: 176px diameter portraits, glassmorphic cards.
 * Gender silhouettes, labeled expand arrows, timeline photo scrubber.
 */

(function() {
    "use strict";

    var svg, g, zoomBehavior;
    var allNodes = [];
    var currentPersonId = "";
    var showTheory = "true";
    var communityPrefix = "";
    var photoPeople = []; // People from photo navigation (for smart subtree)
    var baseNodeIds = {};
    var expandedDirs = {};
    var isFirstRender = true; // Track first render for expand arrow pulse
    var photoIndex = {}; // Track current face photo index per person {personId: index}

    // --- PHOTO-DOMINANT layout: HUGE faces, minimal chrome ---
    var CARD_W = 220, CARD_H = 290;
    var PHOTO_R = 88;                      // 176px diameter — impossible to miss
    var PHOTO_CX = CARD_W / 2;            // Centered
    var PHOTO_CY = 12 + PHOTO_R;          // 12px top pad + radius = 100
    var NAME_Y1 = PHOTO_CY + PHOTO_R + 16; // First name
    var NAME_Y2 = NAME_Y1 + 19;            // Last name
    var DATE_Y  = NAME_Y2 + 16;            // Lifespan
    var CARD_RX = 18;

    var V_GAP = 360;
    var H_GAP = 50;
    var COUPLE_GAP = 24;
    var DROP_Y = 40;
    var EXPAND_R = 18;

    var COLORS = {
        svgBg:        "#080d1a",
        cardBg:       "rgba(15, 20, 32, 0.25)",
        cardBorder:   "rgba(148, 163, 184, 0.08)",
        cardHover:    "rgba(22, 32, 55, 0.92)",
        cardHoverBdr: "rgba(148, 163, 184, 0.25)",
        focalBorder:  "#d4a574",
        focalGlow:    "rgba(212, 165, 116, 0.4)",
        nameText:     "#e8edf5",
        dateText:     "#8b9ab5",
        line:         "rgba(148, 163, 184, 0.7)",    // BOLD and visible
        coupleLine:   "rgba(212, 165, 116, 0.75)",
        coupleDot:    "#d4a574",
        expandBg:     "#4f46e5",
        expandLabel:  "#c7d2fe",
        collapseBg:   "#7c3aed",
        photoBg:      "#111827",
        photoInitial: "#3b4a64",
        genderM:      "#60a5fa",
        genderF:      "#f9a8d4",
        genderU:      "#4b5e78",
        faceBadge:    "#d4a574"
    };

    // --- Initialization ---
    window.initRhodesliTree = function(personId, theory, peopleList, prefix) {
        currentPersonId = personId;
        showTheory = theory;
        photoPeople = peopleList || [];
        communityPrefix = prefix || "";
        setupSearch();
        setupPopupDismiss();
        setupKeyboard();
        setupTimeline();
        loadTreeData(personId, 2);
    };

    // --- Data Loading ---
    function loadTreeData(personId, depth) {
        var loading = document.getElementById("tree-loading");
        if (loading) loading.style.display = "block";

        var url = communityPrefix + "/api/tree/data?depth=" + (depth || 1) + "&show_theory=" + showTheory;
        if (personId) url += "&person_id=" + encodeURIComponent(personId);
        if (photoPeople && photoPeople.length > 1) url += "&people=" + encodeURIComponent(photoPeople.join(","));

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
                // Track photo people for highlighting
                if (data.photo_people && data.photo_people.length > 0) {
                    photoPeople = data.photo_people;
                }
                baseNodeIds = {};
                expandedDirs = {};
                allNodes.forEach(function(n) { baseNodeIds[n.id] = true; });
                renderTree(currentPersonId);
                updateTimeline();
            })
            .catch(function(err) {
                if (loading) loading.style.display = "none";
                console.error("Tree load failed:", err);
            });
    }

    function expandNode(personId, direction) {
        var key = personId + "|" + direction;
        var url = communityPrefix + "/api/tree/expand?person_id=" + encodeURIComponent(personId)
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
                updateTimeline();
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
        updateTimeline();
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
                // Merge face data
                if (nn.data["all_faces"] && nn.data["all_faces"].length > 0) {
                    existing.data["all_faces"] = nn.data["all_faces"];
                    existing.data["face_count"] = nn.data["face_count"];
                }
                // Merge shared photos
                if (nn.data["shared_photos"]) {
                    existing.data["shared_photos"] = existing.data["shared_photos"] || {};
                    Object.keys(nn.data["shared_photos"]).forEach(function(k) {
                        existing.data["shared_photos"][k] = nn.data["shared_photos"][k];
                    });
                }
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

    // --- Shared photos helper ---
    function _getSharedPhotos(nodeA, nodeB) {
        var sp = (nodeA && nodeA.data && nodeA.data.shared_photos) || {};
        var idB = nodeB ? nodeB.id : "";
        return sp[idB] || 0;
    }

    function _maxSharedPhotosParentChild(parentNodes, childNodes, nodeMap) {
        var maxSp = 0;
        parentNodes.forEach(function(pid) {
            var pNode = nodeMap[pid];
            if (!pNode) return;
            childNodes.forEach(function(cid) {
                var sp = _getSharedPhotos(pNode, { id: cid });
                if (sp > maxSp) maxSp = sp;
            });
        });
        return maxSp;
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
                        var leftId = grp[ci].id;
                        var rightId = grp[ci + 1].id;
                        var sp = _getSharedPhotos(grp[ci], grp[ci + 1]);
                        connections.push({
                            type: "couple",
                            x1: leftPos.x + CARD_W,
                            y1: leftPos.y + PHOTO_CY,
                            x2: rightPos.x,
                            y2: rightPos.y + PHOTO_CY,
                            midX: (leftPos.x + CARD_W + rightPos.x) / 2,
                            personA: leftId, personB: rightId,
                            sharedPhotos: sp
                        });
                    }
                }
            });
        });

        // Parent-child T-shape connections
        // Track which parent pairs we've already drawn children for
        var drawnChildPairs = {};

        // Helper: push parent-child connections with shared photos metadata
        function pushParentChildConns(parentIds, childIds, parentX, parentY) {
            var pcSp = _maxSharedPhotosParentChild(parentIds, childIds, nodeMap);
            var childPos = [];
            childIds.forEach(function(cid) {
                var cp = positions[cid];
                if (cp) childPos.push({ x: cp.x + CARD_W / 2, y: cp.y });
            });
            if (childPos.length === 0) return;

            var barY = parentY + DROP_Y;
            connections.push({ type: "drop", x: parentX, y1: parentY, y2: barY,
                               relLabel: "Parent \u2192 Child", sharedPhotos: pcSp, parentIds: parentIds, childIds: childIds });
            var minCX = Math.min.apply(null, childPos.map(function(c) { return c.x; }));
            var maxCX = Math.max.apply(null, childPos.map(function(c) { return c.x; }));
            if (childPos.length > 1) {
                connections.push({ type: "bar", y: barY, x1: minCX, x2: maxCX,
                                   relLabel: "Parent \u2192 Child", sharedPhotos: pcSp });
            }
            if (parentX < minCX || parentX > maxCX) {
                connections.push({ type: "bar", y: barY, x1: Math.min(parentX, minCX), x2: Math.max(parentX, maxCX),
                                   relLabel: "Parent \u2192 Child", sharedPhotos: pcSp });
            }
            childPos.forEach(function(cp) {
                connections.push({ type: "childDrop", x: cp.x, y1: barY, y2: cp.y,
                                   relLabel: "Parent \u2192 Child", sharedPhotos: pcSp });
            });
        }

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

            // For multiple spouses, figure out which children belong to which spouse
            // by checking if the child's other parent is one of the spouses
            if (spouses.length > 1) {
                // Group children by spouse
                var childrenBySpouse = {};
                var unpairedChildren = [];
                spouses.forEach(function(sid) { childrenBySpouse[sid] = []; });

                children.forEach(function(cid) {
                    var childNode = nodeMap[cid];
                    if (!childNode) return;
                    var matched = false;
                    spouses.forEach(function(sid) {
                        // Check if this child has the spouse as a parent
                        if (childNode.rels.father === sid || childNode.rels.mother === sid) {
                            childrenBySpouse[sid].push(cid);
                            matched = true;
                        }
                    });
                    if (!matched) unpairedChildren.push(cid);
                });

                // Draw T-connections for each spouse group
                spouses.forEach(function(sid) {
                    var spouseChildren = childrenBySpouse[sid];
                    if (spouseChildren.length === 0) return;
                    var pairKey = [n.id, sid].sort().join("|");
                    if (drawnChildPairs[pairKey]) return;
                    drawnChildPairs[pairKey] = true;

                    var sp = positions[sid];
                    var parentX = (nPos.x + CARD_W / 2 + sp.x + CARD_W / 2) / 2;
                    var parentY = nPos.y + CARD_H;
                    pushParentChildConns([n.id, sid], spouseChildren, parentX, parentY);
                });

                // Draw unpaired children from the first spouse midpoint (fallback)
                if (unpairedChildren.length > 0 && spouses.length > 0) {
                    var sp = positions[spouses[0]];
                    var parentX = sp ? (nPos.x + CARD_W / 2 + sp.x + CARD_W / 2) / 2 : nPos.x + CARD_W / 2;
                    var parentY = nPos.y + CARD_H;
                    pushParentChildConns([n.id, spouses[0]], unpairedChildren, parentX, parentY);
                }
            } else {
                // Single or no spouse — original logic
                var parentX, parentY;
                if (spouses.length > 0 && positions[spouses[0]]) {
                    var sp = positions[spouses[0]];
                    parentX = (nPos.x + CARD_W / 2 + sp.x + CARD_W / 2) / 2;
                    parentY = nPos.y + CARD_H;
                } else {
                    parentX = nPos.x + CARD_W / 2;
                    parentY = nPos.y + CARD_H;
                }

                var parentIds = spouses.length > 0 ? [n.id, spouses[0]] : [n.id];
                var childPositions = [];
                children.forEach(function(cid) {
                    var cp = positions[cid];
                    if (cp) childPositions.push({ x: cp.x + CARD_W / 2, y: cp.y });
                });
                if (childPositions.length === 0) return;

                var pcSp = _maxSharedPhotosParentChild(parentIds, children, nodeMap);
                var barY = parentY + DROP_Y;
                connections.push({ type: "drop", x: parentX, y1: parentY, y2: barY,
                                   relLabel: "Parent \u2192 Child", sharedPhotos: pcSp, parentIds: parentIds, childIds: children });

                var minCX = Math.min.apply(null, childPositions.map(function(c) { return c.x; }));
                var maxCX = Math.max.apply(null, childPositions.map(function(c) { return c.x; }));
                if (childPositions.length > 1) {
                    connections.push({ type: "bar", y: barY, x1: minCX, x2: maxCX,
                                       relLabel: "Parent \u2192 Child", sharedPhotos: pcSp });
                }
                if (parentX < minCX || parentX > maxCX) {
                    connections.push({ type: "bar", y: barY, x1: Math.min(parentX, minCX), x2: Math.max(parentX, maxCX),
                                       relLabel: "Parent \u2192 Child", sharedPhotos: pcSp });
                }
                childPositions.forEach(function(cp) {
                    connections.push({ type: "childDrop", x: cp.x, y1: barY, y2: cp.y,
                                       relLabel: "Parent \u2192 Child", sharedPhotos: pcSp });
                });
            }
        });

        return { positions: positions, connections: connections, couples: couples,
                 genKeys: genKeys, genOf: genOf, nodeMap: nodeMap };
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
                .scaleExtent([0.08, 3])
                .on("zoom", function(event) {
                    g.attr("transform", event.transform);
                    var k = event.transform.k;
                    // Hide dates earlier at low zoom, but keep names visible longer
                    g.selectAll(".date-label").attr("opacity", k > 0.4 ? 1 : 0);
                    g.selectAll(".name-label").attr("opacity", k > 0.15 ? 1 : 0);
                    g.selectAll(".expand-btn").attr("opacity", k > 0.15 ? 1 : 0);
                    g.selectAll(".face-badge").attr("opacity", k > 0.3 ? 1 : 0);
                    g.selectAll(".photo-cycle-btn").attr("opacity", k > 0.4 ? 1 : 0);
                    g.selectAll(".photo-dots").attr("opacity", k > 0.4 ? 1 : 0);
                    g.selectAll(".generation-bands").attr("opacity", k > 0.1 ? 1 : 0);
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
        glow.append("feGaussianBlur").attr("stdDeviation", "8").attr("result", "blur");
        var glowMerge = glow.append("feMerge");
        glowMerge.append("feMergeNode").attr("in", "blur");
        glowMerge.append("feMergeNode").attr("in", "SourceGraphic");

        // Hover shadow
        var shadow = defs.append("filter").attr("id", "hoverShadow")
            .attr("x", "-15%").attr("y", "-15%").attr("width", "140%").attr("height", "150%");
        shadow.append("feDropShadow").attr("dx", "0").attr("dy", "8").attr("stdDeviation", "14")
            .attr("flood-color", "rgba(0,0,0,0.6)").attr("flood-opacity", "0.6");

        // Photo shadow for depth
        var photoShadow = defs.append("filter").attr("id", "photoShadow")
            .attr("x", "-20%").attr("y", "-10%").attr("width", "140%").attr("height", "140%");
        photoShadow.append("feDropShadow").attr("dx", "0").attr("dy", "4").attr("stdDeviation", "6")
            .attr("flood-color", "rgba(0,0,0,0.55)").attr("flood-opacity", "0.55");

        // Clip paths — rounded rect (squircle) to show more face area
        Object.keys(positions).forEach(function(pid) {
            defs.append("clipPath")
                .attr("id", "clip-" + pid.replace(/[^a-zA-Z0-9]/g, "_"))
                .append("rect")
                .attr("x", PHOTO_CX - PHOTO_R)
                .attr("y", PHOTO_CY - PHOTO_R)
                .attr("width", PHOTO_R * 2)
                .attr("height", PHOTO_R * 2)
                .attr("rx", PHOTO_R * 0.25)
                .attr("ry", PHOTO_R * 0.25);
        });

        // --- Generation bands (alternating subtle backgrounds) ---
        var genKeys = layout.genKeys;
        var genOf = layout.genOf;
        if (genKeys.length > 0) {
            var bandGroup = g.append("g").attr("class", "generation-bands");
            // Compute x extent across ALL positions
            var allXs = Object.keys(positions).map(function(pid) { return positions[pid].x; });
            var minX = Math.min.apply(null, allXs) - H_GAP * 2;
            var maxX = Math.max.apply(null, allXs) + CARD_W + H_GAP * 2;
            var bandColors = ["rgba(148, 163, 184, 0.04)", "rgba(99, 131, 176, 0.04)"];
            var genLabels = {};
            // Assign generation labels relative to focal generation (gen 0)
            genKeys.forEach(function(gk) {
                if (gk < 0) genLabels[gk] = Math.abs(gk) === 1 ? "Parents" : (Math.abs(gk) === 2 ? "Grandparents" : "Gen " + gk);
                else if (gk === 0) genLabels[gk] = "Focal";
                else genLabels[gk] = gk === 1 ? "Children" : (gk === 2 ? "Grandchildren" : "Gen +" + gk);
            });
            genKeys.forEach(function(gk, gi) {
                var y = gk * V_GAP;
                var bandY = y - 30;
                var bandH = CARD_H + 60;
                bandGroup.append("rect")
                    .attr("x", minX).attr("y", bandY)
                    .attr("width", maxX - minX).attr("height", bandH)
                    .attr("fill", bandColors[gi % 2])
                    .attr("rx", 12).attr("ry", 12)
                    .attr("opacity", 0)
                    .transition().duration(800).ease(d3.easeCubicOut)
                    .attr("opacity", 1);
                // Generation label on the left
                bandGroup.append("text")
                    .attr("x", minX + 16).attr("y", bandY + 22)
                    .attr("fill", "rgba(148, 163, 184, 0.35)")
                    .attr("font-size", "13px")
                    .attr("font-family", "Georgia, serif")
                    .attr("font-style", "italic")
                    .text(genLabels[gk] || "Gen " + gk)
                    .attr("opacity", 0)
                    .transition().delay(400).duration(600).ease(d3.easeCubicOut)
                    .attr("opacity", 1);
            });
        }

        // --- Stroke width from shared photos (min 2, max 5) ---
        function connStrokeWidth(c) {
            var sp = c.sharedPhotos || 0;
            if (sp <= 0) return 2;
            if (sp >= 4) return 5;
            // Linear scale: 1 photo = 2.75, 2 = 3.5, 3 = 4.25, 4+ = 5
            return 2 + sp * 0.75;
        }

        // --- Hover tooltip text ---
        function connTooltip(c) {
            var label = c.relLabel || (c.type === "couple" ? "Spouse" : "");
            var sp = c.sharedPhotos || 0;
            var parts = [];
            if (label) parts.push(label);
            if (sp > 0) parts.push(sp + " shared photo" + (sp !== 1 ? "s" : ""));
            return parts.join(" \u2014 ") || "";
        }

        // --- Draw connections (BOLD and VISIBLE) with draw-in animation ---
        var lineGroup = g.append("g").attr("class", "connections");
        connections.forEach(function(c, ci) {
            var lineEl;
            var sw = connStrokeWidth(c);
            var tip = connTooltip(c);
            if (c.type === "couple") {
                lineEl = lineGroup.append("line")
                    .attr("x1", c.x1).attr("y1", c.y1).attr("x2", c.x2).attr("y2", c.y2)
                    .attr("stroke", COLORS.coupleLine).attr("stroke-width", sw)
                    .attr("stroke-dasharray", "10,6");
                if (tip) lineEl.append("title").text(tip);
                // Couple dot fades in after line draws
                var dot = lineGroup.append("circle")
                    .attr("cx", c.midX).attr("cy", c.y1).attr("r", 5)
                    .attr("fill", COLORS.coupleDot)
                    .attr("opacity", 0);
                dot.transition().delay(600 + ci * 20).duration(300)
                    .ease(d3.easeCubicOut).attr("opacity", 1);
            } else if (c.type === "drop" || c.type === "childDrop") {
                lineEl = lineGroup.append("line")
                    .attr("x1", c.x).attr("y1", c.y1).attr("x2", c.x).attr("y2", c.y2)
                    .attr("stroke", COLORS.line).attr("stroke-width", sw);
                if (tip) lineEl.append("title").text(tip);
            } else if (c.type === "bar") {
                lineEl = lineGroup.append("line")
                    .attr("x1", c.x1).attr("y1", c.y).attr("x2", c.x2).attr("y2", c.y)
                    .attr("stroke", COLORS.line).attr("stroke-width", sw);
                if (tip) lineEl.append("title").text(tip);
            }
            // Animate line drawing in via stroke-dashoffset
            if (lineEl) {
                var lineNode = lineEl.node();
                var lineLen = lineNode.getTotalLength ? lineNode.getTotalLength() : 200;
                // For couple lines, preserve the dashed pattern; for others, use solid draw-in
                if (c.type !== "couple") {
                    lineEl
                        .attr("stroke-dasharray", lineLen)
                        .attr("stroke-dashoffset", lineLen);
                    lineEl.transition()
                        .delay(ci * 15)
                        .duration(600)
                        .ease(d3.easeCubicOut)
                        .attr("stroke-dashoffset", 0);
                } else {
                    // For couple lines, fade in instead (dasharray is decorative)
                    lineEl.attr("opacity", 0);
                    lineEl.transition()
                        .delay(ci * 15)
                        .duration(600)
                        .ease(d3.easeCubicOut)
                        .attr("opacity", 1);
                }
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
            // Start slightly below and invisible for entrance animation
            .attr("transform", function(d) { return "translate(" + d.x + "," + (d.y + 20) + ")"; })
            .style("cursor", "pointer")
            .attr("opacity", 0)
            .on("click", function(event, d) {
                event.stopPropagation();
                showNodePopup(event, d.node.data, d.id);
            });

        // Staggered card entrance: fade in from below
        cards.each(function(d, i) {
            d3.select(this).transition()
                .delay(i * 40)
                .duration(400)
                .ease(d3.easeCubicOut)
                .attr("transform", "translate(" + d.x + "," + d.y + ")")
                .attr("opacity", 1);
        });

        // Hover: card materializes, photo ring grows, show photo cycling arrows
        cards.on("mouseenter", function() {
                var card = d3.select(this);
                card.select(".card-bg").transition().duration(200)
                    .attr("fill", COLORS.cardHover)
                    .attr("stroke", COLORS.cardHoverBdr)
                    .attr("filter", "url(#hoverShadow)");
                card.select(".photo-ring").transition().duration(200)
                    .attr("stroke-width", 5);
                card.transition().duration(200)
                    .attr("transform", function(d) {
                        return "translate(" + d.x + "," + (d.y - 5) + ")";
                    });
                // Reveal photo cycling arrows and dots on hover
                card.selectAll(".photo-cycle-btn").transition().duration(200).attr("opacity", 0.7);
                card.selectAll(".photo-dots").transition().duration(200).attr("opacity", 0.8);
            })
            .on("mouseleave", function(event, d) {
                var card = d3.select(this);
                var isFocal = d.id === currentPersonId;
                card.select(".card-bg").transition().duration(300)
                    .attr("fill", COLORS.cardBg)
                    .attr("stroke", isFocal ? COLORS.focalBorder : COLORS.cardBorder)
                    .attr("filter", null);
                card.select(".photo-ring").transition().duration(300)
                    .attr("stroke-width", 3.5);
                card.transition().duration(300)
                    .attr("transform", function(d) {
                        return "translate(" + d.x + "," + d.y + ")";
                    });
                // Hide photo cycling arrows and dots
                card.selectAll(".photo-cycle-btn").transition().duration(300).attr("opacity", 0);
                card.selectAll(".photo-dots").transition().duration(300).attr("opacity", 0);
            });

        // Card background
        cards.append("rect")
            .attr("class", "card-bg")
            .attr("width", CARD_W).attr("height", CARD_H)
            .attr("rx", CARD_RX).attr("ry", CARD_RX)
            .attr("fill", COLORS.cardBg)
            .attr("stroke", function(d) {
                if (d.id === focalId) return COLORS.focalBorder;
                if (photoPeople && photoPeople.indexOf(d.id) >= 0) return "rgba(212, 165, 116, 0.5)";
                return COLORS.cardBorder;
            })
            .attr("stroke-width", function(d) {
                if (d.id === focalId) return 2.5;
                if (photoPeople && photoPeople.indexOf(d.id) >= 0) return 2;
                return 1;
            });

        // Focal person outer glow
        cards.each(function(d) {
            if (d.id === focalId) {
                d3.select(this).insert("rect", ":first-child")
                    .attr("x", PHOTO_CX - PHOTO_R - 10)
                    .attr("y", PHOTO_CY - PHOTO_R - 10)
                    .attr("width", PHOTO_R * 2 + 20)
                    .attr("height", PHOTO_R * 2 + 20)
                    .attr("rx", PHOTO_R * 0.25 + 10)
                    .attr("ry", PHOTO_R * 0.25 + 10)
                    .attr("fill", "none").attr("stroke", COLORS.focalGlow)
                    .attr("stroke-width", 5)
                    .attr("filter", "url(#focalGlow)");
            }
        });

        // Photo — THE STAR. Shadow + image + gender ring + face count badge.
        cards.each(function(d) {
            var el = d3.select(this);
            var clipId = "clip-" + d.id.replace(/[^a-zA-Z0-9]/g, "_");
            var faces = d.node.data.all_faces || [];
            var faceIdx = photoIndex[d.id] || 0;
            if (faceIdx >= faces.length) faceIdx = 0;
            var photoUrl = faces.length > 0 ? faces[faceIdx].url : (d.node.data.avatar || d.node.data.photo_url);

            // Gender — declare BEFORE use in silhouette fallback and ring
            var gender = d.node.data.gender || "U";
            var ringColor = gender === "M" ? COLORS.genderM : gender === "F" ? COLORS.genderF : COLORS.genderU;

            // Shadow — rounded rect
            el.append("rect")
                .attr("x", PHOTO_CX - PHOTO_R - 1)
                .attr("y", PHOTO_CY - PHOTO_R - 1)
                .attr("width", PHOTO_R * 2 + 2)
                .attr("height", PHOTO_R * 2 + 2)
                .attr("rx", PHOTO_R * 0.25 + 1)
                .attr("ry", PHOTO_R * 0.25 + 1)
                .attr("fill", "rgba(0,0,0,0.35)")
                .attr("filter", "url(#photoShadow)");

            if (photoUrl) {
                // Primary image (crossfadeable via timeline)
                el.append("image")
                    .attr("class", "face-primary")
                    .attr("x", PHOTO_CX - PHOTO_R).attr("y", PHOTO_CY - PHOTO_R)
                    .attr("width", PHOTO_R * 2).attr("height", PHOTO_R * 2)
                    .attr("href", photoUrl)
                    .attr("clip-path", "url(#" + clipId + ")")
                    .attr("preserveAspectRatio", "xMidYMid slice")
                    .style("transition", "opacity 0.5s cubic-bezier(0.4, 0, 0.2, 1)");
                // Secondary image layer for crossfade
                if (faces.length > 1) {
                    el.append("image")
                        .attr("class", "face-secondary")
                        .attr("x", PHOTO_CX - PHOTO_R).attr("y", PHOTO_CY - PHOTO_R)
                        .attr("width", PHOTO_R * 2).attr("height", PHOTO_R * 2)
                        .attr("href", photoUrl)
                        .attr("clip-path", "url(#" + clipId + ")")
                        .attr("preserveAspectRatio", "xMidYMid slice")
                        .style("opacity", "0")
                        .style("transition", "opacity 0.5s cubic-bezier(0.4, 0, 0.2, 1)");
                }
            } else {
                // Gender silhouette avatar — Ancestry-style
                var silColor = gender === "M" ? COLORS.genderM : gender === "F" ? COLORS.genderF : COLORS.genderU;
                var silBg = gender === "M" ? "rgba(96,165,250,0.15)" : gender === "F" ? "rgba(249,168,212,0.15)" : "rgba(75,94,120,0.15)";
                el.append("rect")
                    .attr("x", PHOTO_CX - PHOTO_R)
                    .attr("y", PHOTO_CY - PHOTO_R)
                    .attr("width", PHOTO_R * 2)
                    .attr("height", PHOTO_R * 2)
                    .attr("rx", PHOTO_R * 0.25)
                    .attr("ry", PHOTO_R * 0.25)
                    .attr("fill", silBg);
                // Head
                el.append("circle")
                    .attr("cx", PHOTO_CX).attr("cy", PHOTO_CY - PHOTO_R * 0.18)
                    .attr("r", PHOTO_R * 0.32)
                    .attr("fill", silColor).attr("opacity", 0.55);
                // Shoulders
                el.append("ellipse")
                    .attr("cx", PHOTO_CX).attr("cy", PHOTO_CY + PHOTO_R * 0.52)
                    .attr("rx", PHOTO_R * 0.52).attr("ry", PHOTO_R * 0.35)
                    .attr("fill", silColor).attr("opacity", 0.4)
                    .attr("clip-path", "url(#" + clipId + ")");
                // Initial letter overlay for personalization
                var initial = (d.node.data["first name"] || "?")[0].toUpperCase();
                el.append("text")
                    .attr("x", PHOTO_CX).attr("y", PHOTO_CY + PHOTO_R * 0.05)
                    .attr("text-anchor", "middle").attr("dy", "0.35em")
                    .attr("fill", silColor).attr("opacity", 0.25)
                    .attr("font-size", PHOTO_R * 0.6 + "px").attr("font-weight", "700")
                    .attr("font-family", "Georgia, serif")
                    .text(initial);
            }

            // Gender ring — bold rounded-rect border
            el.append("rect")
                .attr("class", "photo-ring")
                .attr("x", PHOTO_CX - PHOTO_R)
                .attr("y", PHOTO_CY - PHOTO_R)
                .attr("width", PHOTO_R * 2)
                .attr("height", PHOTO_R * 2)
                .attr("rx", PHOTO_R * 0.25)
                .attr("ry", PHOTO_R * 0.25)
                .attr("fill", "none").attr("stroke", ringColor).attr("stroke-width", 3.5);

            // Face count badge (top-right of photo)
            var faceCount = d.node.data.face_count || 0;
            if (faceCount > 1) {
                var badgeG = el.append("g")
                    .attr("class", "face-badge")
                    .attr("transform", "translate(" + (PHOTO_CX + PHOTO_R - 14) + "," + (PHOTO_CY - PHOTO_R + 10) + ")");
                badgeG.append("circle").attr("r", 14)
                    .attr("fill", COLORS.faceBadge).attr("stroke", COLORS.svgBg).attr("stroke-width", 2.5);
                badgeG.append("text").attr("text-anchor", "middle").attr("dy", "0.35em")
                    .attr("fill", "#080d1a").attr("font-size", "12px").attr("font-weight", "700")
                    .attr("font-family", "'Inter', system-ui, sans-serif")
                    .text(faceCount);
            }

            // --- Photo cycling arrows (left/right) — appear on hover ---
            if (faces.length > 1) {
                var currentIdx = faceIdx;

                // Left arrow
                var leftArrow = el.append("g")
                    .attr("class", "photo-cycle-btn photo-cycle-left")
                    .attr("transform", "translate(" + (PHOTO_CX - PHOTO_R - 2) + "," + PHOTO_CY + ")")
                    .style("cursor", "pointer")
                    .attr("opacity", 0);
                leftArrow.append("circle").attr("r", 22)
                    .attr("fill", "rgba(0,0,0,0.6)").attr("stroke", "rgba(255,255,255,0.3)").attr("stroke-width", 1);
                leftArrow.append("text").attr("text-anchor", "middle").attr("dy", "0.35em")
                    .attr("fill", "white").attr("font-size", "18px").attr("font-weight", "700")
                    .text("\u2039");
                leftArrow.on("click", function(event) {
                    event.stopPropagation();
                    cyclePhoto(d.id, d.node.data, -1);
                });

                // Right arrow
                var rightArrow = el.append("g")
                    .attr("class", "photo-cycle-btn photo-cycle-right")
                    .attr("transform", "translate(" + (PHOTO_CX + PHOTO_R + 2) + "," + PHOTO_CY + ")")
                    .style("cursor", "pointer")
                    .attr("opacity", 0);
                rightArrow.append("circle").attr("r", 22)
                    .attr("fill", "rgba(0,0,0,0.6)").attr("stroke", "rgba(255,255,255,0.3)").attr("stroke-width", 1);
                rightArrow.append("text").attr("text-anchor", "middle").attr("dy", "0.35em")
                    .attr("fill", "white").attr("font-size", "18px").attr("font-weight", "700")
                    .text("\u203A");
                rightArrow.on("click", function(event) {
                    event.stopPropagation();
                    cyclePhoto(d.id, d.node.data, 1);
                });

                // Dot indicator below photo
                var dotGroup = el.append("g")
                    .attr("class", "photo-dots")
                    .attr("transform", "translate(" + PHOTO_CX + "," + (PHOTO_CY + PHOTO_R + 8) + ")")
                    .attr("opacity", 0);
                var dotSpacing = 10;
                var dotsWidth = (faces.length - 1) * dotSpacing;
                faces.forEach(function(f, fi) {
                    dotGroup.append("circle")
                        .attr("class", "photo-dot")
                        .attr("cx", -dotsWidth / 2 + fi * dotSpacing)
                        .attr("cy", 0)
                        .attr("r", fi === currentIdx ? 3.5 : 2.5)
                        .attr("fill", fi === currentIdx ? "#d4a574" : "rgba(255,255,255,0.4)");
                });
            }
        });

        // First name — large and readable
        cards.append("text")
            .attr("class", "name-label name-first")
            .attr("x", CARD_W / 2).attr("y", NAME_Y1)
            .attr("text-anchor", "middle")
            .attr("fill", "#f1f5f9")
            .attr("font-size", "17px").attr("font-weight", "600")
            .attr("font-family", "'Inter', system-ui, -apple-system, sans-serif")
            .style("text-shadow", "0 1px 3px rgba(0,0,0,0.6)")
            .text(function(d) {
                var first = d.node.data["first name"] || "";
                // Truncate to fit card width (~18 chars at 17px)
                return first.length > 16 ? first.substring(0, 14) + "\u2026" : first;
            });

        // Last name
        cards.append("text")
            .attr("class", "name-label name-last")
            .attr("x", CARD_W / 2).attr("y", NAME_Y2)
            .attr("text-anchor", "middle")
            .attr("fill", "#e2e8f0")
            .attr("font-size", "14.5px").attr("font-weight", "500")
            .attr("font-family", "'Inter', system-ui, -apple-system, sans-serif")
            .style("text-shadow", "0 1px 2px rgba(0,0,0,0.5)")
            .text(function(d) {
                var last = d.node.data["last name"] || "";
                return last.length > 18 ? last.substring(0, 16) + "\u2026" : last;
            });

        // Lifespan — higher contrast white text with shadow
        cards.append("text")
            .attr("class", "date-label")
            .attr("x", CARD_W / 2).attr("y", DATE_Y)
            .attr("text-anchor", "middle")
            .attr("fill", "#cbd5e1").attr("font-size", "13px")
            .attr("font-family", "'Inter', system-ui, -apple-system, sans-serif")
            .attr("letter-spacing", "0.04em")
            .style("text-shadow", "0 1px 2px rgba(0,0,0,0.5)")
            .text(function(d) { return d.node.data.lifespan || ""; });

        // --- Expand/collapse arrows — LARGE, LABELED, UNMISSABLE ---
        // Now works from ANY node, not just the focal person
        var arrowGroup = g.append("g").attr("class", "expand-arrows");
        var expandArrowCount = 0;
        nodeData.forEach(function(d) {
            var data = d.node.data;
            var cx = d.x + CARD_W / 2;
            var dirs = [
                { flag: "has_more_parents", dir: "parents", label: "Parents", arrowDir: "up", ax: cx, ay: d.y - 34 },
                { flag: "has_more_children", dir: "children", label: "Children", arrowDir: "down", ax: cx, ay: d.y + CARD_H + 34 },
                { flag: "has_more_siblings", dir: "siblings", label: "Siblings", arrowDir: "left", ax: d.x - 34, ay: d.y + CARD_H / 2 }
            ];
            dirs.forEach(function(dd) {
                var key = d.id + "|" + dd.dir;
                var isExpanded = expandedDirs.hasOwnProperty(key);
                // Show expand arrow if the node has hidden connections in this direction,
                // OR if it has has_hidden_connections generic flag and this direction makes sense
                var showArrow = data[dd.flag] || isExpanded;
                if (!showArrow && data.has_hidden_connections && !isExpanded) {
                    // For generic has_hidden_connections, show a generic expand button below the card
                    if (dd.dir === "children") showArrow = true;
                }
                if (showArrow) {
                    drawExpandArrow(arrowGroup, dd.ax, dd.ay, dd.arrowDir, d.id, dd.dir, isExpanded, dd.label, isFirstRender && !isExpanded);
                    expandArrowCount++;
                }
            });
        });

        // Stop pulsing expand arrows after 3 seconds on first render
        if (isFirstRender && expandArrowCount > 0) {
            setTimeout(function() {
                arrowGroup.selectAll(".expand-pulse").classed("expand-pulse", false);
            }, 3000);
        }
        isFirstRender = false;

        fitToContent();
    }

    function drawExpandArrow(parent, cx, cy, direction, personId, expandDir, isCollapse, label, shouldPulse) {
        var grp = parent.append("g")
            .attr("class", "expand-btn" + (shouldPulse ? " expand-pulse" : ""))
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

        // Large pill-shaped button — Ancestry-style expand
        var pillW = isCollapse ? 36 : 100;
        var pillH = 34;
        grp.append("rect")
            .attr("x", -pillW / 2).attr("y", -pillH / 2)
            .attr("width", pillW).attr("height", pillH)
            .attr("rx", pillH / 2).attr("ry", pillH / 2)
            .attr("fill", isCollapse ? COLORS.collapseBg : COLORS.expandBg)
            .attr("stroke", "rgba(255,255,255,0.15)").attr("stroke-width", 1.5);

        if (isCollapse) {
            // Minus icon
            grp.append("line").attr("x1", -7).attr("y1", 0).attr("x2", 7).attr("y2", 0)
                .attr("stroke", "white").attr("stroke-width", 2.5).attr("stroke-linecap", "round");
        } else {
            // Arrow + label
            var arrowChar = direction === "up" ? "\u25B2" : direction === "down" ? "\u25BC" : "\u25C0";
            grp.append("text")
                .attr("x", -pillW / 2 + 16).attr("y", 0)
                .attr("text-anchor", "middle").attr("dy", "0.35em")
                .attr("fill", "rgba(255,255,255,0.7)").attr("font-size", "9px")
                .text(arrowChar);
            grp.append("text")
                .attr("x", 6).attr("y", 0)
                .attr("text-anchor", "middle").attr("dy", "0.35em")
                .attr("fill", "white").attr("font-size", "12px").attr("font-weight", "600")
                .attr("font-family", "'Inter', system-ui, sans-serif")
                .text(label || expandDir);
        }

        // Hover glow
        grp.on("mouseenter", function() {
            d3.select(this).select("rect").transition().duration(150)
                .attr("fill", isCollapse ? "#8b5cf6" : "#6366f1")
                .attr("stroke", "rgba(255,255,255,0.35)");
        }).on("mouseleave", function() {
            d3.select(this).select("rect").transition().duration(200)
                .attr("fill", isCollapse ? COLORS.collapseBg : COLORS.expandBg)
                .attr("stroke", "rgba(255,255,255,0.15)");
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
        // Never zoom out below 0.25 — faces must stay visible
        var scale = Math.max(Math.min(scaleX, scaleY, 1.0), 0.25);
        var tx = w / 2 - (bbox.x + bbox.width / 2) * scale;
        var ty = h / 2 - (bbox.y + bbox.height / 2) * scale;
        svg.transition().duration(800).ease(d3.easeCubicInOut).call(
            zoomBehavior.transform,
            d3.zoomIdentity.translate(tx, ty).scale(scale)
        );
    }

    // --- Timeline slider for photo scrubbing ---
    var lastDisplayedYear = null;

    function setupTimeline() {
        var slider = document.getElementById("timeline-slider");
        if (!slider) return;

        // Inject CSS for the slider track fill + year pulse animation
        if (!document.getElementById("timeline-anim-styles")) {
            var styleEl = document.createElement("style");
            styleEl.id = "timeline-anim-styles";
            styleEl.textContent = [
                // Active track fill via gradient
                "#timeline-slider { -webkit-appearance: none; appearance: none; background: transparent; }",
                "#timeline-slider::-webkit-slider-runnable-track {",
                "  height: 6px; border-radius: 3px;",
                "  background: linear-gradient(to right,",
                "    #d4a574 0%, #d4a574 var(--fill-pct, 50%),",
                "    rgba(148,163,184,0.18) var(--fill-pct, 50%),",
                "    rgba(148,163,184,0.18) 100%);",
                "  transition: background 0.1s ease;",
                "}",
                "#timeline-slider::-moz-range-track {",
                "  height: 6px; border-radius: 3px;",
                "  background: linear-gradient(to right,",
                "    #d4a574 0%, #d4a574 var(--fill-pct, 50%),",
                "    rgba(148,163,184,0.18) var(--fill-pct, 50%),",
                "    rgba(148,163,184,0.18) 100%);",
                "}",
                "#timeline-slider::-webkit-slider-thumb {",
                "  -webkit-appearance: none; appearance: none;",
                "  width: 18px; height: 18px; border-radius: 50%;",
                "  background: #d4a574; border: 2px solid #080d1a;",
                "  margin-top: -6px; cursor: pointer;",
                "  box-shadow: 0 0 8px rgba(212,165,116,0.4);",
                "  transition: transform 0.15s ease, box-shadow 0.15s ease;",
                "}",
                "#timeline-slider::-moz-range-thumb {",
                "  width: 18px; height: 18px; border-radius: 50%;",
                "  background: #d4a574; border: 2px solid #080d1a;",
                "  cursor: pointer;",
                "  box-shadow: 0 0 8px rgba(212,165,116,0.4);",
                "}",
                "#timeline-slider:active::-webkit-slider-thumb {",
                "  transform: scale(1.25);",
                "  box-shadow: 0 0 14px rgba(212,165,116,0.7);",
                "}",
                // Year counter pulse on decade boundary
                "@keyframes yearPulse {",
                "  0%   { transform: scale(1); color: #d4a574; }",
                "  40%  { transform: scale(1.15); color: #f5d4ae; }",
                "  100% { transform: scale(1); color: #d4a574; }",
                "}",
                ".year-pulse { animation: yearPulse 0.35s ease-out; }",
                // Expand arrow pulse
                "@keyframes expandPulse {",
                "  0%   { transform: scale(1); filter: brightness(1); }",
                "  50%  { transform: scale(1.08); filter: brightness(1.3); }",
                "  100% { transform: scale(1); filter: brightness(1); }",
                "}",
                ".expand-pulse rect {",
                "  animation: expandPulse 1s ease-in-out 3;",
                "}"
            ].join("\n");
            document.head.appendChild(styleEl);
        }

        slider.addEventListener("input", function() {
            var year = parseInt(slider.value);
            updateSliderFill(slider);
            updateYearDisplay(year);
            scrubPhotos(year);
        });
    }

    function updateSliderFill(slider) {
        var min = parseFloat(slider.min) || 0;
        var max = parseFloat(slider.max) || 100;
        var val = parseFloat(slider.value) || 0;
        var pct = ((val - min) / (max - min)) * 100;
        slider.style.setProperty("--fill-pct", pct + "%");
    }

    function updateYearDisplay(year) {
        var yearEl = document.getElementById("timeline-year");
        if (!yearEl) return;
        yearEl.textContent = "c. " + year;

        // Pulse on decade boundary crossing
        var prevDecade = lastDisplayedYear ? Math.floor(lastDisplayedYear / 10) : null;
        var curDecade = Math.floor(year / 10);
        if (prevDecade !== null && prevDecade !== curDecade) {
            yearEl.classList.remove("year-pulse");
            // Force reflow to restart animation
            void yearEl.offsetWidth;
            yearEl.classList.add("year-pulse");
        }
        lastDisplayedYear = year;
    }

    function updateTimeline() {
        var bar = document.getElementById("timeline-bar");
        var slider = document.getElementById("timeline-slider");
        var ticksEl = document.getElementById("timeline-ticks");
        if (!bar || !slider) return;

        // Find people with multiple faces and parse birth years (API returns strings)
        var hasMulti = false;
        var minYear = 9999, maxYear = 0;
        allNodes.forEach(function(n) {
            var faces = n.data.all_faces || [];
            if (faces.length > 1) hasMulti = true;
            var bday = parseInt(n.data.birthday, 10);
            if (bday && bday > 1800 && bday < 2030) {
                if (bday < minYear) minYear = bday;
                if (bday + 60 > maxYear) maxYear = bday + 60;
            }
        });

        if (!hasMulti && allNodes.length < 3) {
            bar.classList.add("hidden");
            return;
        }

        // Fallback defaults if no valid birth years found
        if (minYear > maxYear) { minYear = 1890; maxYear = 1980; }

        // Show timeline for any tree with people
        bar.classList.remove("hidden");
        minYear = Math.max(1860, minYear - 10);
        maxYear = Math.min(2025, maxYear + 10);
        slider.min = minYear;
        slider.max = maxYear;
        // Start at the earliest photo era (beginning of range)
        slider.value = minYear;

        var yearEl = document.getElementById("timeline-year");
        if (yearEl) yearEl.textContent = "c. " + slider.value;
        lastDisplayedYear = parseInt(slider.value);
        updateSliderFill(slider);

        // Decade ticks
        if (ticksEl) {
            var html = "";
            for (var decade = Math.ceil(minYear / 10) * 10; decade <= maxYear; decade += 10) {
                html += "<span>" + decade + "</span>";
            }
            ticksEl.innerHTML = html;
        }

        // Hide hint after first interaction
        slider.addEventListener("input", function hideHint() {
            var hint = document.getElementById("timeline-hint");
            if (hint) hint.style.display = "none";
            slider.removeEventListener("input", hideHint);
        }, { once: true });
    }

    var scrubState = {}; // Track which face index is showing per person
    var scrubTransitioning = {}; // Track in-flight crossfades to prevent overlap

    // --- Per-person photo cycling via arrow buttons ---
    function cyclePhoto(personId, nodeData, direction) {
        var faces = nodeData.all_faces || [];
        if (faces.length <= 1) return;

        var currentIdx = photoIndex[personId] || 0;
        var newIdx = (currentIdx + direction + faces.length) % faces.length;
        photoIndex[personId] = newIdx;
        scrubState[personId] = newIdx; // Keep scrub state in sync

        // Crossfade to new photo
        var nodeEl = g.selectAll(".person-node").filter(function(d) { return d.id === personId; });
        var primary = nodeEl.select(".face-primary");
        var secondary = nodeEl.select(".face-secondary");

        if (secondary.empty() || primary.empty()) {
            // No secondary layer — just swap primary
            if (!primary.empty()) primary.attr("href", faces[newIdx].url);
            updatePhotoDots(personId, newIdx, faces.length);
            return;
        }

        if (scrubTransitioning[personId]) {
            // If already transitioning, force-finish and swap
            primary.attr("href", faces[newIdx].url);
            primary.style("opacity", "1");
            secondary.style("opacity", "0");
            scrubTransitioning[personId] = false;
            updatePhotoDots(personId, newIdx, faces.length);
            return;
        }

        var newUrl = faces[newIdx].url;
        secondary.attr("href", newUrl);
        scrubTransitioning[personId] = true;

        requestAnimationFrame(function() {
            requestAnimationFrame(function() {
                secondary.style("opacity", "1");
                primary.style("opacity", "0");

                var secNode = secondary.node();
                var handler = function onTransitionEnd(e) {
                    if (e.propertyName !== "opacity") return;
                    secNode.removeEventListener("transitionend", onTransitionEnd);
                    primary.style("transition", "none");
                    primary.attr("href", newUrl);
                    primary.style("opacity", "1");
                    secondary.style("transition", "none");
                    secondary.style("opacity", "0");
                    requestAnimationFrame(function() {
                        primary.style("transition", "opacity 0.4s ease");
                        secondary.style("transition", "opacity 0.4s ease");
                        scrubTransitioning[personId] = false;
                    });
                };
                secNode.addEventListener("transitionend", handler);

                setTimeout(function() {
                    if (scrubTransitioning[personId]) {
                        secNode.removeEventListener("transitionend", handler);
                        primary.attr("href", newUrl);
                        primary.style("opacity", "1");
                        secondary.style("opacity", "0");
                        scrubTransitioning[personId] = false;
                    }
                }, 500);
            });
        });

        updatePhotoDots(personId, newIdx, faces.length);
    }

    function updatePhotoDots(personId, activeIdx, totalFaces) {
        var nodeEl = g.selectAll(".person-node").filter(function(d) { return d.id === personId; });
        var dots = nodeEl.selectAll(".photo-dot");
        dots.each(function(dot, i) {
            d3.select(this)
                .attr("r", i === activeIdx ? 3.5 : 2.5)
                .attr("fill", i === activeIdx ? "#d4a574" : "rgba(255,255,255,0.4)");
        });
    }

    function scrubPhotos(year) {
        // For each person with multiple faces, cycle through based on year position
        allNodes.forEach(function(n) {
            var faces = n.data.all_faces || [];
            if (faces.length <= 1) return;

            // Distribute faces evenly across the person's likely lifespan
            var bday = n.data.birthday;
            var birthYear = (typeof bday === "number" && bday > 1800) ? bday : 1900;
            var spanStart = birthYear;
            var spanEnd = birthYear + Math.max(faces.length * 10, 60);

            // Determine which face to show based on where the year falls
            var fraction = Math.max(0, Math.min(1, (year - spanStart) / (spanEnd - spanStart)));
            var faceIdx = Math.min(Math.floor(fraction * faces.length), faces.length - 1);

            // Skip if already showing this face
            var prevIdx = scrubState[n.id];
            if (prevIdx === faceIdx) return;
            scrubState[n.id] = faceIdx;
            photoIndex[n.id] = faceIdx; // Keep photo cycling in sync
            updatePhotoDots(n.id, faceIdx, faces.length);

            // Skip if a crossfade is already in flight for this person
            if (scrubTransitioning[n.id]) return;

            // Crossfade using CSS transitions + transitionend event
            var nodeEl = g.selectAll(".person-node").filter(function(d) { return d.id === n.id; });
            var primary = nodeEl.select(".face-primary");
            var secondary = nodeEl.select(".face-secondary");

            if (secondary.empty() || primary.empty()) return;

            var newUrl = faces[faceIdx].url;
            var personId = n.id;

            // Set secondary to new image, then crossfade
            secondary.attr("href", newUrl);
            scrubTransitioning[personId] = true;

            // Use requestAnimationFrame to ensure the browser has processed the new href
            requestAnimationFrame(function() {
                requestAnimationFrame(function() {
                    // Fade secondary in, primary out simultaneously
                    secondary.style("opacity", "1");
                    primary.style("opacity", "0");

                    // Listen for transition end on the secondary element
                    var secNode = secondary.node();
                    var handler = function onTransitionEnd(e) {
                        if (e.propertyName !== "opacity") return;
                        secNode.removeEventListener("transitionend", onTransitionEnd);
                        // Swap primary to new image, reset opacities instantly
                        primary.style("transition", "none");
                        primary.attr("href", newUrl);
                        primary.style("opacity", "1");
                        secondary.style("transition", "none");
                        secondary.style("opacity", "0");
                        // Restore transitions on next frame
                        requestAnimationFrame(function() {
                            primary.style("transition", "opacity 0.4s ease");
                            secondary.style("transition", "opacity 0.4s ease");
                            scrubTransitioning[personId] = false;
                        });
                    };
                    secNode.addEventListener("transitionend", handler);

                    // Safety fallback: if transitionend never fires (e.g., opacity was already 1)
                    // clear transitioning state after 500ms
                    setTimeout(function() {
                        if (scrubTransitioning[personId]) {
                            secNode.removeEventListener("transitionend", handler);
                            primary.attr("href", newUrl);
                            primary.style("opacity", "1");
                            secondary.style("opacity", "0");
                            scrubTransitioning[personId] = false;
                        }
                    }, 500);
                });
            });
        });
    }

    // --- Node Action Popup ---
    function showNodePopup(event, nodeData, nodeId) {
        var popup = document.getElementById("tree-node-popup");
        if (!popup) return;

        var name = ((nodeData["first name"] || "") + " " + (nodeData["last name"] || "")).trim();
        var photoUrl = nodeData.avatar || (nodeData.all_faces && nodeData.all_faces.length > 0 ? nodeData.all_faces[0].url : "") || nodeData.photo_url || "";
        var gender = nodeData.gender || "U";
        var ringColor = gender === "M" ? COLORS.genderM : gender === "F" ? COLORS.genderF : COLORS.genderU;
        var faceCount = nodeData.face_count || 0;

        var html = '<div style="display:flex;align-items:center;gap:12px;padding:12px 16px;border-bottom:1px solid #1e293b;margin-bottom:6px">';
        if (photoUrl) {
            html += '<img src="' + photoUrl + '" style="width:56px;height:56px;border-radius:22%;object-fit:cover;border:3px solid ' + ringColor + '" />';
        } else {
            html += '<div style="width:56px;height:56px;border-radius:22%;background:#1a2336;border:3px solid ' + ringColor + ';display:flex;align-items:center;justify-content:center;color:#4b5e7a;font-family:Georgia,serif;font-size:22px">' + (name[0] || "?").toUpperCase() + '</div>';
        }
        html += '<div><span style="font-weight:600;color:#f1f5f9;font-size:16px;font-family:Georgia,serif;display:block">' + name + '</span>';
        if (faceCount > 1) {
            html += '<span style="font-size:12px;color:#d4a574">' + faceCount + ' photos</span>';
        }
        var lifespan = nodeData.lifespan || "";
        if (lifespan) {
            html += '<span style="font-size:11px;color:#8b9ab5;display:block;margin-top:2px">' + lifespan + '</span>';
        }
        html += '</div></div>';

        // Always show View Profile and Focus Tree
        if (nodeData.identity_url)
            html += '<a href="' + nodeData.identity_url + '">View Profile</a>';
        html += '<button data-action="tree-focus" data-person-id="' + nodeId + '">Focus Tree Here</button>';

        // Expand buttons — show when there's more to load
        var hasExpandOptions = false;
        if (nodeData["has_more_parents"]) {
            html += '<button data-action="tree-expand" data-person-id="' + nodeId + '" data-direction="parents">\u25B2 Show Parents</button>';
            hasExpandOptions = true;
        }
        if (nodeData["has_more_children"]) {
            html += '<button data-action="tree-expand" data-person-id="' + nodeId + '" data-direction="children">\u25BC Show Children</button>';
            hasExpandOptions = true;
        }
        if (nodeData["has_more_siblings"]) {
            html += '<button data-action="tree-expand" data-person-id="' + nodeId + '" data-direction="siblings">\u25C0 Show Siblings</button>';
            hasExpandOptions = true;
        }
        // If no expand options, show a hint
        if (!hasExpandOptions && !nodeData.identity_url) {
            html += '<div style="padding:6px 14px;color:#4b5e78;font-size:11px;font-style:italic">All known connections loaded</div>';
        }

        popup.innerHTML = html;
        popup.classList.remove("hidden");

        var x = event.clientX + 14, y = event.clientY + 14;
        if (x + 260 > window.innerWidth) x = window.innerWidth - 270;
        if (y + 320 > window.innerHeight) y = window.innerHeight - 330;
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
                if (svg && zoomBehavior) svg.transition().duration(350).ease(d3.easeCubicOut).call(zoomBehavior.scaleBy, 1.4);
            } else if (action === "tree-zoom-out") {
                if (svg && zoomBehavior) svg.transition().duration(350).ease(d3.easeCubicOut).call(zoomBehavior.scaleBy, 0.7);
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
                svg.transition().duration(250).ease(d3.easeQuadOut).call(zoomBehavior.scaleBy, 1.3);
            } else if (e.key === "-" && svg && zoomBehavior) {
                e.preventDefault();
                svg.transition().duration(250).ease(d3.easeQuadOut).call(zoomBehavior.scaleBy, 0.7);
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
                fetch(communityPrefix + "/api/tree/search?q=" + encodeURIComponent(q))
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
                window.history.pushState({}, "", communityPrefix + "/tree?person=" + encodeURIComponent(pid));
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
