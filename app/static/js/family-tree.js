/**
 * family-tree.js — Rhodesli family tree wrapper using CardSvg API.
 * Uses f3.createChart() with CardSvg for reliable SVG-based cards.
 *
 * AD-175: CardSvg used for compatibility (CardHtml silently fails in
 * current family-chart build). Session 79 fix.
 */

window.setupFamilyTree = function (data, containerSelector, rootPersonId) {
    var container = document.querySelector(containerSelector);
    if (!container || !data || data.length === 0) return;

    if (typeof f3 === 'undefined') {
        console.error("family-chart library not loaded!");
        return;
    }

    // Set main_id on the first matching person (or first in list)
    var mainId = rootPersonId || data[0].id;
    var mainDatum = data.find(function(d) { return d.id === mainId; });
    if (mainDatum) {
        mainDatum.data.main = true;
    }

    // Create chart with CardSvg (CardHtml is broken in this library build)
    var chart = f3.createChart(containerSelector, data)
        .setTransitionTime(800);

    var card = chart.setCard(f3.CardSvg);
    card.setCardDisplay([
        function(d) { return (d.data["first name"] || "") + " " + (d.data["last name"] || ""); },
        function(d) { return d.data["lifespan"] || ""; }
    ]);
    card.setMiniTree(true);

    // On card click: re-center tree on that person
    card.setOnCardClick(function(e, d) {
        chart.updateMainId(d.data.id);
        chart.updateTree({});
    });

    chart.updateTree({ initial: true });
};
