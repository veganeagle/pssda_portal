// Renders the two /search dashboard charts (province trend, sector donut)
// from the JSON the server embeds in #dashboard-data. Pure progressive
// enhancement: if the data block or an SVG mount point is missing, this is a
// no-op and the rest of the page (bento cards, table) still renders fine from
// server-side HTML alone.
(function () {
  var dataEl = document.getElementById("dashboard-data");
  if (!dataEl) return;
  var data = JSON.parse(dataEl.textContent);

  var SECTOR_COLORS = [
    "#2f6f6b", "#b8831e", "#6b8f3f", "#8b5fb8", "#c2574a",
    "#3f7fb8", "#9a8f3f", "#5f8f8f", "#b85f8f", "#7a7a7a", "#4f6f9f",
  ];

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  // Both series share one zero-based y-scale per column band so the bars
  // (headcount) and the line (payroll) read honestly off the same x grid,
  // each against its own max — a standard dual-axis combo chart.
  function colScale(values, h, padT, padB) {
    var max = Math.max.apply(null, values);
    return function (v) { return h - padB - (v / (max || 1)) * (h - padT - padB); };
  }

  function barsRects(values, w, h, padT, padB, color) {
    var n = values.length, stepX = w / n, barW = stepX * 0.5;
    var sy = colScale(values, h, padT, padB);
    var base = h - padB;
    return values.map(function (v, i) {
      var x = i * stepX + (stepX - barW) / 2, y = sy(v);
      return '<rect x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" width="' + barW.toFixed(1) +
        '" height="' + (base - y).toFixed(1) + '" fill="' + color + '" rx="1.5"/>';
    }).join("");
  }

  function linePath(values, w, h, padT, padB) {
    var n = values.length, stepX = w / n;
    var sy = colScale(values, h, padT, padB);
    var pts = values.map(function (v, i) { return [i * stepX + stepX / 2, sy(v)]; });
    return pts.map(function (p, i) { return (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" ");
  }

  function renderTrend() {
    var svg = document.getElementById("dashboard-trend-chart");
    if (!svg || !data.trend) return;
    var vb = svg.viewBox.baseVal, w = vb.width, h = vb.height;
    var headcounts = data.trend.map(function (d) { return d.headcount; });
    var payrolls = data.trend.map(function (d) { return d.total_payroll; });
    var bars = barsRects(headcounts, w, h, 10, 34, cssVar("--mute") || "#5f6b7a");
    var pPath = linePath(payrolls, w, h, 10, 34);
    var accent = cssVar("--accent") || "#c8752b";
    var ink = cssVar("--text") || "#1c2733";
    var first = data.trend[0], last = data.trend[data.trend.length - 1];
    svg.innerHTML =
      '<g opacity="0.45">' + bars + '</g>' +
      '<path d="' + pPath + '" fill="none" stroke="' + accent + '" stroke-width="2.75" stroke-linejoin="round"/>' +
      '<text x="2" y="' + (h - 20) + '" font-size="11" fill="' + ink + '" font-family="JetBrains Mono, monospace">' + first.year + '</text>' +
      '<text x="' + (w - 2) + '" y="' + (h - 20) + '" font-size="11" fill="' + ink + '" font-family="JetBrains Mono, monospace" text-anchor="end">' + last.year + '</text>' +
      '<text x="2" y="' + (h - 6) + '" font-size="11" fill="' + cssVar("--mute") + '" font-family="JetBrains Mono, monospace">' +
        (headcounts[0] / 1000).toFixed(0) + 'K people &middot; $' + (payrolls[0] / 1e9).toFixed(1) + 'B</text>' +
      '<text x="' + (w - 2) + '" y="' + (h - 6) + '" font-size="11" fill="' + cssVar("--mute") + '" font-family="JetBrains Mono, monospace" text-anchor="end">' +
        (headcounts[headcounts.length - 1] / 1000).toFixed(0) + 'K people &middot; $' + (payrolls[payrolls.length - 1] / 1e9).toFixed(1) + 'B</text>';
  }

  function renderDonut() {
    var svg = document.getElementById("dashboard-sector-donut");
    var legend = document.getElementById("dashboard-sector-legend");
    if (!svg || !data.sectors) return;
    var total = data.sectors.reduce(function (a, s) { return a + s.total_payroll; }, 0);
    var r = 15.9, cx = 21, cy = 21;
    var circumference = 2 * Math.PI * r;
    var offset = 0;
    var segs = "";
    data.sectors.forEach(function (s, i) {
      var frac = s.total_payroll / total;
      var len = frac * circumference;
      var color = SECTOR_COLORS[i % SECTOR_COLORS.length];
      segs += '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="' + color +
        '" stroke-width="7" stroke-dasharray="' + len.toFixed(2) + ' ' + (circumference - len).toFixed(2) +
        '" stroke-dashoffset="' + (-offset).toFixed(2) + '" transform="rotate(-90 ' + cx + ' ' + cy + ')"/>';
      offset += len;
    });
    svg.innerHTML = segs;
    if (legend) {
      legend.innerHTML = data.sectors.map(function (s, i) {
        var pct = (s.total_payroll / total * 100).toFixed(0);
        return '<div class="donut-row"><span class="dot" style="background:' + SECTOR_COLORS[i % SECTOR_COLORS.length] +
          '"></span><span class="n">' + s.sector_name + '</span><span class="v mono">' + pct + '%</span></div>';
      }).join("");
    }
  }

  renderTrend();
  renderDonut();
})();
