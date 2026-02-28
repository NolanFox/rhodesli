/**
 * family-tree.js — Rhodesli family tree with lazy loading, search, zoom.
 * AD-185: API-driven tree with expand/collapse, search, zoom controls.
 * Uses f3.createChart() with CardSvg.
 */

(function() {
    "use strict";

    var chart = null;
    var allNodes = [];
    var currentPersonId = "";
    var showTheory = "true";

    // --- Initialization ---
    window.initRhodesliTree = function(personId, theory) {
        currentPersonId = personId;
        showTheory = theory;
        setupSearch();
        setupZoomControls();
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
                    if (container) container.innerHTML = '<p class="text-center text-slate-400 py-8">No family data found for this person.</p>';
                    return;
                }
                currentPersonId = data.focal_person;
                allNodes = data.nodes;
                renderChart(currentPersonId);
            })
            .catch(function(err) {
                if (loading) loading.style.display = "none";
                console.error("Tree data load failed:", err);
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
                // Update rels for the source person from the response
                var srcNode = data.nodes.find(function(n) { return false; }); // new nodes only
                renderChart(personId);
            });
    }

    function mergeNodes(newNodes) {
        for (var i = 0; i < newNodes.length; i++) {
            var nn = newNodes[i];
            var existing = allNodes.find(function(n) { return n.id === nn.id; });
            if (!existing) {
                allNodes.push(nn);
            } else {
                // Merge rels — expand existing connections
                if (nn.rels.father && !existing.rels.father) existing.rels.father = nn.rels.father;
                if (nn.rels.mother && !existing.rels.mother) existing.rels.mother = nn.rels.mother;
                if (nn.rels.spouses) {
                    existing.rels.spouses = existing.rels.spouses || [];
                    for (var s = 0; s < nn.rels.spouses.length; s++) {
                        if (existing.rels.spouses.indexOf(nn.rels.spouses[s]) === -1)
                            existing.rels.spouses.push(nn.rels.spouses[s]);
                    }
                }
                if (nn.rels.children) {
                    existing.rels.children = existing.rels.children || [];
                    for (var c = 0; c < nn.rels.children.length; c++) {
                        if (existing.rels.children.indexOf(nn.rels.children[c]) === -1)
                            existing.rels.children.push(nn.rels.children[c]);
                    }
                }
                // Update expansion flags
                existing.data["has_more_parents"] = nn.data["has_more_parents"];
                existing.data["has_more_children"] = nn.data["has_more_children"];
                existing.data["has_more_siblings"] = nn.data["has_more_siblings"];
            }
        }
    }

    // --- Chart Rendering ---
    function renderChart(focusId) {
        if (!allNodes || allNodes.length === 0) return;
        if (typeof f3 === "undefined") { console.error("family-chart not loaded"); return; }

        var mainId = focusId || allNodes[0].id;

        // Clear main flags, set new main
        for (var i = 0; i < allNodes.length; i++) {
            allNodes[i].data.main = (allNodes[i].id === mainId);
        }

        if (chart) {
            // Update existing chart
            chart.updateData(allNodes);
            chart.updateMainId(mainId);
            chart.updateTree({});
        } else {
            // Create new chart
            var container = document.getElementById("tree-container");
            if (!container) return;
            container.innerHTML = "";
            chart = f3.createChart("#tree-container", allNodes)
                .setTransitionTime(600);
            var card = chart.setCard(f3.CardSvg);
            card.setCardDisplay([
                function(d) { return (d.data["first name"] || "") + " " + (d.data["last name"] || ""); },
                function(d) { return d.data["lifespan"] || ""; }
            ]);
            card.setMiniTree(true);

            // Card click: show action popup
            card.setOnCardClick(function(e, d) {
                showNodePopup(e, d.data);
            });

            chart.updateTree({ initial: true });
        }
    }

    // --- Node Action Popup ---
    function showNodePopup(event, nodeData) {
        var popup = document.getElementById("tree-node-popup");
        if (!popup) return;

        var name = (nodeData["first name"] || "") + " " + (nodeData["last name"] || "");
        var html = '<div style="font-weight:600;padding:4px 10px;color:#1e293b;font-size:13px;border-bottom:1px solid #e2e8f0;margin-bottom:4px">' + name.trim() + '</div>';

        // View Profile (only for archive identities)
        if (nodeData.identity_url) {
            html += '<a href="' + nodeData.identity_url + '">View Profile</a>';
        }

        // Focus tree on this person
        html += '<button data-action="tree-focus" data-person-id="' + nodeData.id + '">Focus Tree Here</button>';

        // Expand options
        if (nodeData["has_more_parents"]) {
            html += '<button data-action="tree-expand" data-person-id="' + nodeData.id + '" data-direction="parents">Expand Parents</button>';
        }
        if (nodeData["has_more_children"]) {
            html += '<button data-action="tree-expand" data-person-id="' + nodeData.id + '" data-direction="children">Expand Children</button>';
        }
        if (nodeData["has_more_siblings"]) {
            html += '<button data-action="tree-expand" data-person-id="' + nodeData.id + '" data-direction="siblings">Expand Siblings</button>';
        }

        popup.innerHTML = html;
        popup.classList.remove("hidden");

        // Position near the click
        var x = event.clientX + 10;
        var y = event.clientY + 10;
        // Keep on screen
        if (x + 200 > window.innerWidth) x = window.innerWidth - 210;
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
        // Dismiss popup on click outside
        document.addEventListener("click", function(e) {
            var popup = document.getElementById("tree-node-popup");
            if (popup && !popup.contains(e.target)) {
                hideNodePopup();
            }
        });

        // Handle popup button clicks via event delegation
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
                var dir = btn.getAttribute("data-direction");
                expandNode(personId, dir);
            } else if (action === "tree-zoom-in") {
                zoomIn();
            } else if (action === "tree-zoom-out") {
                zoomOut();
            } else if (action === "tree-fit") {
                fitToScreen();
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
            if (q.length < 2) {
                results.classList.add("hidden");
                results.innerHTML = "";
                return;
            }
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
                        for (var i = 0; i < data.results.length; i++) {
                            var r = data.results[i];
                            var badge = r.has_photo ? "Archive" : "GEDCOM";
                            html += '<div class="result-item" data-person-id="' + r.id + '">'
                                + '<span class="name">' + r.name + '</span> '
                                + '<span class="badge">(' + badge + ')</span></div>';
                        }
                        results.innerHTML = html;
                        results.classList.remove("hidden");
                    });
            }, 250);
        });

        // Click search result → load that person's tree
        results.addEventListener("click", function(e) {
            var item = e.target.closest(".result-item");
            if (!item) return;
            var pid = item.getAttribute("data-person-id");
            if (pid) {
                input.value = item.querySelector(".name").textContent;
                results.classList.add("hidden");
                loadTreeData(pid, 2);
                // Update URL without reload
                var url = "/tree?person=" + encodeURIComponent(pid);
                window.history.pushState({}, "", url);
            }
        });

        // Hide results on blur (with delay for click)
        input.addEventListener("blur", function() {
            setTimeout(function() { results.classList.add("hidden"); }, 200);
        });

        // Show results on focus if input has value
        input.addEventListener("focus", function() {
            if (results.innerHTML && input.value.trim().length >= 2)
                results.classList.remove("hidden");
        });
    }

    // --- Zoom Controls ---
    function getTreeSvg() {
        var container = document.getElementById("tree-container");
        return container ? container.querySelector("svg") : null;
    }

    function zoomIn() {
        var svg = getTreeSvg();
        if (!svg || !d3) return;
        d3.select(svg).transition().duration(300).call(
            d3.zoom().on("zoom", function() {}).scaleBy, 1.3
        );
    }

    function zoomOut() {
        var svg = getTreeSvg();
        if (!svg || !d3) return;
        d3.select(svg).transition().duration(300).call(
            d3.zoom().on("zoom", function() {}).scaleBy, 0.7
        );
    }

    function fitToScreen() {
        // Re-render with initial fit
        if (chart) {
            chart.updateTree({ tree_position: "fit" });
        }
    }

    // --- Theory Toggle ---
    document.addEventListener("change", function(e) {
        if (e.target && e.target.id === "tree-show-theory") {
            showTheory = e.target.checked ? "true" : "false";
            loadTreeData(currentPersonId, 2);
        }
    });

})();
