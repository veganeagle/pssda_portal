// Renders the home dashboard's two charts from the JSON the server embeds in
// #dashboard-data, via the shared renderers in charts.js (loaded before this
// file — see home.html). Pure progressive enhancement: if the data block or
// an SVG mount point is missing, this is a no-op and the rest of the page
// (bento cards, table) still renders fine from server-side HTML alone.
(function () {
  var dataEl = document.getElementById("dashboard-data");
  if (!dataEl) return;
  var data = JSON.parse(dataEl.textContent);

  if (data.trend) window.renderTrendChart("dashboard-trend-chart", data.trend);
  if (data.sectors) {
    var items = data.sectors.map(function (s) { return {name: s.sector_name, value: s.total_payroll}; });
    window.renderDonutChart("dashboard-sector-donut", "dashboard-sector-legend", items);
  }
})();
