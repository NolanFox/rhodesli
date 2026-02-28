/**
 * family-tree.js — Rhodesli heritage family tree.
 * AD-185: Custom D3 tree — circular portraits, dark theme, lazy loading.
 * No f3/family-chart dependency. Pure D3 v7.
 */

(function() {
    "use strict";

    var svg, g, zoomBehavior;
    var allNodes = [];
    var currentPersonId = "";
    var showTheory = "true";
    var NODE_R = 40;            // Portrait radius
    var FOCAL_R = 52;           // Focal person radius
    var V_GAP = 160;            // Vertical gap between generations
    var H_GAP = 110;            // Horizontal gap between siblings
    var SPOUSE_GAP = 16;        // Gap between spouses

    // --- Initialization ---
    window.initRhodesliTree = function(personId, theory) {
        currentPersonId = personId;
        showTheory = theory;
        setupSearch();
        setupPopupDismiss();
        setupZoomControls();
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
                renderTree(personId);
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

        // BFS from focal to assign generations
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

            // Parents = gen - 1
            [node.rels.father, node.rels.mother].forEach(function(pid) {
                if (pid && !visited.hasOwnProperty(pid)) {
                    visited[pid] = gen - 1;
                    queue.push({ id: pid, gen: gen - 1 });
                }
            });
            // Children = gen + 1
            (node.rels.children || []).forEach(function(cid) {
                if (!visited.hasOwnProperty(cid)) {
                    visited[cid] = gen + 1;
                    queue.push({ id: cid, gen: gen + 1 });
                }
            });
            // Spouses = same gen
            (node.rels.spouses || []).forEach(function(sid) {
                if (!visited.hasOwnProperty(sid)) {
                    visited[sid] = gen;
                    queue.push({ id: sid, gen: gen });
                }
            });
        }

        return { generations: generations, genOf: visited, nodeMap: nodeMap };
    }

    // --- Layout: assign x,y to each node ---
    function layoutNodes(focalId) {
        var h = buildHierarchy(focalId);
        var gens = h.generations;
        var genOf = h.genOf;
        var nodeMap = h.nodeMap;

        // Sort generation keys
        var genKeys = Object.keys(gens).map(Number).sort(function(a, b) { return a - b; });

        var positions = {};
        var links = [];

        // Layout each generation
        genKeys.forEach(function(gk) {
            var people = gens[gk];
            // Group spouses together
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

            // Calculate total width needed
            var totalWidth = 0;
            groups.forEach(function(grp, i) {
                totalWidth += grp.length * (NODE_R * 2 + SPOUSE_GAP);
                if (i > 0) totalWidth += H_GAP;
            });

            // Center horizontally
            var x = -totalWidth / 2;
            var y = gk * V_GAP;

            groups.forEach(function(grp, gi) {
                if (gi > 0) x += H_GAP;
                grp.forEach(function(person, pi) {
                    if (pi > 0) x += SPOUSE_GAP;
                    x += NODE_R;
                    positions[person.id] = { x: x, y: y, node: person };
                    x += NODE_R;
                });
            });
        });

        // Build links: parent->child, spouse connections
        allNodes.forEach(function(n) {
            var nPos = positions[n.id];
            if (!nPos) return;
            // Children links
            (n.rels.children || []).forEach(function(cid) {
                var cPos = positions[cid];
                if (cPos) links.push({ source: nPos, target: cPos, type: "parent" });
            });
            // Spouse links
            (n.rels.spouses || []).forEach(function(sid) {
                var sPos = positions[sid];
                if (sPos && n.id < sid) { // only draw once
                    links.push({ source: nPos, target: sPos, type: "spouse" });
                }
            });
        });

        return { positions: positions, links: links };
    }

    // --- Render ---
    function renderTree(focalId) {
        if (!allNodes || allNodes.length === 0) return;

        var container = document.getElementById("tree-container");
        if (!container) return;

        var layout = layoutNodes(focalId);
        var positions = layout.positions;
        var links = layout.links;

        // Create or reuse SVG
        if (!svg) {
            container.innerHTML = "";
            var w = container.clientWidth;
            var h = container.clientHeight;

            svg = d3.select(container).append("svg")
                .attr("width", w)
                .attr("height", h)
                .style("background", "#1e293b");

            g = svg.append("g");

            zoomBehavior = d3.zoom()
                .scaleExtent([0.15, 3])
                .on("zoom", function(event) {
                    g.attr("transform", event.transform);
                });
            svg.call(zoomBehavior);

            // Resize handler
            window.addEventListener("resize", function() {
                var newW = container.clientWidth;
                var newH = container.clientHeight;
                svg.attr("width", newW).attr("height", newH);
            });
        }

        // Clear previous content
        g.selectAll("*").remove();

        // Define clip path for circular portraits
        var defs = g.append("defs");
        Object.keys(positions).forEach(function(pid) {
            var r = pid === focalId ? FOCAL_R : NODE_R;
            defs.append("clipPath")
                .attr("id", "clip-" + pid.replace(/[^a-zA-Z0-9]/g, "_"))
                .append("circle")
                .attr("r", r);
        });

        // Draw links
        var linkGroup = g.append("g").attr("class", "links");

        links.forEach(function(link) {
            if (link.type === "parent") {
                // Curved parent-child line
                var sx = link.source.x, sy = link.source.y;
                var tx = link.target.x, ty = link.target.y;
                var my = (sy + ty) / 2;
                linkGroup.append("path")
                    .attr("d", "M" + sx + "," + (sy + NODE_R + 4) +
                          " C" + sx + "," + my + " " + tx + "," + my + " " + tx + "," + (ty - NODE_R - 4))
                    .attr("fill", "none")
                    .attr("stroke", "#475569")
                    .attr("stroke-width", 1.5)
                    .attr("opacity", 0.7);
            } else if (link.type === "spouse") {
                // Horizontal spouse connector with heart
                var sx = link.source.x, sy = link.source.y;
                var tx = link.target.x;
                var mx = (sx + tx) / 2;
                linkGroup.append("line")
                    .attr("x1", sx + NODE_R + 2).attr("y1", sy)
                    .attr("x2", tx - NODE_R - 2).attr("y2", sy)
                    .attr("stroke", "#d4a574")
                    .attr("stroke-width", 1.5)
                    .attr("stroke-dasharray", "4,3")
                    .attr("opacity", 0.6);
            }
        });

        // Draw nodes
        var nodeData = Object.keys(positions).map(function(pid) {
            return { id: pid, x: positions[pid].x, y: positions[pid].y, node: positions[pid].node };
        });

        var nodeGroup = g.append("g").attr("class", "nodes");

        var nodes = nodeGroup.selectAll(".person-node")
            .data(nodeData, function(d) { return d.id; })
            .enter()
            .append("g")
            .attr("class", "person-node")
            .attr("transform", function(d) { return "translate(" + d.x + "," + d.y + ")"; })
            .style("cursor", "pointer")
            .on("click", function(event, d) {
                event.stopPropagation();
                showNodePopup(event, d.node.data, d.id);
            });

        // Background ring (glow for focal person)
        nodes.append("circle")
            .attr("r", function(d) { return (d.id === focalId ? FOCAL_R : NODE_R) + 3; })
            .attr("fill", "none")
            .attr("stroke", function(d) {
                if (d.id === focalId) return "#d4a574";
                return d.node.data.photo_url ? "#334155" : "#1e293b";
            })
            .attr("stroke-width", function(d) { return d.id === focalId ? 3 : 1.5; })
            .attr("opacity", function(d) { return d.id === focalId ? 1 : 0.8; });

        // Face photo (circular)
        nodes.each(function(d) {
            var el = d3.select(this);
            var r = d.id === focalId ? FOCAL_R : NODE_R;
            var clipId = "clip-" + d.id.replace(/[^a-zA-Z0-9]/g, "_");

            if (d.node.data.photo_url) {
                el.append("image")
                    .attr("x", -r).attr("y", -r)
                    .attr("width", r * 2).attr("height", r * 2)
                    .attr("href", d.node.data.photo_url)
                    .attr("clip-path", "url(#" + clipId + ")")
                    .attr("preserveAspectRatio", "xMidYMid slice");
            } else {
                // Placeholder circle with initial
                el.append("circle")
                    .attr("r", r)
                    .attr("fill", "#334155");
                var initial = (d.node.data["first name"] || "?")[0].toUpperCase();
                el.append("text")
                    .attr("text-anchor", "middle")
                    .attr("dy", "0.35em")
                    .attr("fill", "#64748b")
                    .attr("font-size", r * 0.7 + "px")
                    .attr("font-family", "'Georgia', serif")
                    .text(initial);
            }
        });

        // Expand indicator dots
        nodes.each(function(d) {
            var el = d3.select(this);
            var r = d.id === focalId ? FOCAL_R : NODE_R;
            var data = d.node.data;

            if (data["has_more_parents"]) {
                el.append("circle").attr("cx", 0).attr("cy", -(r + 12)).attr("r", 5)
                    .attr("fill", "#6366f1").attr("stroke", "#1e293b").attr("stroke-width", 2);
                el.append("text").attr("x", 0).attr("y", -(r + 8)).attr("text-anchor", "middle")
                    .attr("fill", "white").attr("font-size", "8px").text("+");
            }
            if (data["has_more_children"]) {
                el.append("circle").attr("cx", 0).attr("cy", r + 12).attr("r", 5)
                    .attr("fill", "#6366f1").attr("stroke", "#1e293b").attr("stroke-width", 2);
                el.append("text").attr("x", 0).attr("y", r + 16).attr("text-anchor", "middle")
                    .attr("fill", "white").attr("font-size", "8px").text("+");
            }
        });

        // Name labels
        nodes.append("text")
            .attr("text-anchor", "middle")
            .attr("y", function(d) { return (d.id === focalId ? FOCAL_R : NODE_R) + 18; })
            .attr("fill", "#e2e8f0")
            .attr("font-size", "12px")
            .attr("font-family", "'Georgia', serif")
            .text(function(d) {
                var name = ((d.node.data["first name"] || "") + " " + (d.node.data["last name"] || "")).trim();
                return name.length > 20 ? name.substring(0, 18) + "..." : name;
            });

        // Lifespan labels
        nodes.append("text")
            .attr("text-anchor", "middle")
            .attr("y", function(d) { return (d.id === focalId ? FOCAL_R : NODE_R) + 32; })
            .attr("fill", "#64748b")
            .attr("font-size", "10px")
            .text(function(d) { return d.node.data.lifespan || ""; });

        // Fit to viewport
        fitToContent();
    }

    function fitToContent() {
        if (!g || !svg) return;
        var bbox = g.node().getBBox();
        if (bbox.width === 0 || bbox.height === 0) return;

        var container = document.getElementById("tree-container");
        var w = container.clientWidth;
        var h = container.clientHeight;
        var pad = 60;

        var scaleX = (w - pad * 2) / bbox.width;
        var scaleY = (h - pad * 2) / bbox.height;
        var scale = Math.min(scaleX, scaleY, 1.5); // Don't zoom in too much

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
        var html = '<div style="font-weight:600;padding:6px 12px;color:#e2e8f0;font-size:14px;border-bottom:1px solid #334155;margin-bottom:4px;font-family:Georgia,serif">' + name + '</div>';

        if (nodeData.identity_url) {
            html += '<a href="' + nodeData.identity_url + '">View Profile</a>';
        }
        html += '<button data-action="tree-focus" data-person-id="' + nodeId + '">Focus Tree Here</button>';
        if (nodeData["has_more_parents"])
            html += '<button data-action="tree-expand" data-person-id="' + nodeId + '" data-direction="parents">Expand Parents</button>';
        if (nodeData["has_more_children"])
            html += '<button data-action="tree-expand" data-person-id="' + nodeId + '" data-direction="children">Expand Children</button>';
        if (nodeData["has_more_siblings"])
            html += '<button data-action="tree-expand" data-person-id="' + nodeId + '" data-direction="siblings">Expand Siblings</button>';

        popup.innerHTML = html;
        popup.classList.remove("hidden");

        var x = event.clientX + 12;
        var y = event.clientY + 12;
        if (x + 180 > window.innerWidth) x = window.innerWidth - 190;
        if (y + 200 > window.innerHeight) y = window.innerHeight - 210;
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
                zoomIn();
            } else if (action === "tree-zoom-out") {
                zoomOut();
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

    // --- Zoom ---
    function setupZoomControls() {
        // Scroll wheel zoom is handled by d3.zoom on the SVG
    }

    function zoomIn() {
        if (!svg || !zoomBehavior) return;
        svg.transition().duration(300).call(zoomBehavior.scaleBy, 1.4);
    }

    function zoomOut() {
        if (!svg || !zoomBehavior) return;
        svg.transition().duration(300).call(zoomBehavior.scaleBy, 0.7);
    }

    // --- Theory Toggle ---
    document.addEventListener("change", function(e) {
        if (e.target && e.target.id === "tree-show-theory") {
            showTheory = e.target.checked ? "true" : "false";
            loadTreeData(currentPersonId, 2);
        }
    });

})();
