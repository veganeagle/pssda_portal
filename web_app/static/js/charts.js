// Shared chart renderers used by the home dashboard and every sector page:
//   window.renderTrendChart(svgId, trend, opts) — a zero-based dual-series
//     combo chart (grey bars = headcount, accent line = total payroll), both
//     on their own scale against the same year grid. trend is
//     [{year, headcount, total_payroll}, ...]. opts.countFormat: "k"
//     (default; "405K people" — fine at province scale) or "raw" ("733
//     people" — K-rounding a small sector/employer to "1K" is misleading,
//     not just imprecise).
//   window.renderDonutChart(svgId, legendId, items) — a donut with a legend
//     list underneath, one color per item in order. items is
//     [{name, value}, ...]; the caller decides what "value" means (payroll,
//     headcount, ...) and is responsible for capping the item count (e.g.
//     top 5 + "Other") since the donut doesn't do that itself.
//   window.renderCompareBarChart(svgId, legendId, seriesA, seriesB, labelA,
//     labelB) — grouped bars, one pair per year, for the employer/position
//     comparison pages. seriesA/seriesB: [{year, headcount}, ...], same
//     years in the same order on both.
(function () {
  var DONUT_COLORS = [
    "#2f6f6b", "#b8831e", "#6b8f3f", "#8b5fb8", "#c2574a",
    "#3f7fb8", "#9a8f3f", "#5f8f8f", "#b85f8f", "#7a7a7a", "#4f6f9f",
  ];

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  // Draws in real pixels: the viewBox is set to the SVG's own rendered box (its
  // CSS height and the card's width), so axis text never stretches, and the
  // chart is redrawn at the new size when the window is resized.
  function fitViewBox(svg, redraw) {
    var r = svg.getBoundingClientRect();
    svg.setAttribute("viewBox", "0 0 " + Math.round(r.width) + " " + Math.round(r.height));
    if (!svg.hasAttribute("data-fitted")) {
      svg.setAttribute("data-fitted", "");
      var timer;
      window.addEventListener("resize", function () { clearTimeout(timer); timer = setTimeout(redraw, 150); });
    }
    return svg.viewBox.baseVal;
  }

  function fmtCount(n, mode) {
    return mode === "raw" ? n.toLocaleString() : (n / 1000).toFixed(0) + "K";
  }

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

  window.renderTrendChart = function (svgId, trend, opts) {
    var svg = document.getElementById(svgId);
    if (!svg || !trend || !trend.length) return;
    var countFormat = (opts && opts.countFormat) || "k";
    var vb = fitViewBox(svg, function () { window.renderTrendChart(svgId, trend, opts); }), w = vb.width, h = vb.height;
    var headcounts = trend.map(function (d) { return d.headcount; });
    var payrolls = trend.map(function (d) { return d.total_payroll; });
    var bars = barsRects(headcounts, w, h, 10, 34, cssVar("--mute") || "#5f6b7a");
    var pPath = linePath(payrolls, w, h, 10, 34);
    var accent = cssVar("--accent");
    var ink = cssVar("--text") || "#1c2733";
    var first = trend[0], last = trend[trend.length - 1];
    svg.innerHTML =
      '<g opacity="0.45">' + bars + '</g>' +
      '<path d="' + pPath + '" fill="none" stroke="' + accent + '" stroke-width="2.75" stroke-linejoin="round"/>' +
      '<text x="2" y="' + (h - 20) + '" font-size="11" fill="' + ink + '" font-family="JetBrains Mono, monospace">' + first.year + '</text>' +
      '<text x="' + (w - 2) + '" y="' + (h - 20) + '" font-size="11" fill="' + ink + '" font-family="JetBrains Mono, monospace" text-anchor="end">' + last.year + '</text>' +
      '<text x="2" y="' + (h - 6) + '" font-size="11" fill="' + cssVar("--mute") + '" font-family="JetBrains Mono, monospace">' +
        fmtCount(headcounts[0], countFormat) + ' people &middot; $' + (payrolls[0] / 1e9).toFixed(1) + 'B</text>' +
      '<text x="' + (w - 2) + '" y="' + (h - 6) + '" font-size="11" fill="' + cssVar("--mute") + '" font-family="JetBrains Mono, monospace" text-anchor="end">' +
        fmtCount(headcounts[headcounts.length - 1], countFormat) + ' people &middot; $' + (payrolls[payrolls.length - 1] / 1e9).toFixed(1) + 'B</text>';
  };

  // Grouped bar chart (e.g. disclosed-employee counts for two employers/
  // combos, one pair of bars per year) — a line chart reads as near-flat
  // noise once two series with different scales are forced onto one axis;
  // paired bars per year make each year's comparison legible on its own.
  // seriesA/seriesB: [{year, headcount}, ...], same years in order on both.
  window.renderCompareBarChart = function (svgId, legendId, seriesA, seriesB, labelA, labelB) {
    var svg = document.getElementById(svgId);
    if (!svg || !seriesA || !seriesA.length || !seriesB || !seriesB.length) return;
    var vb = fitViewBox(svg, function () {
      window.renderCompareBarChart(svgId, legendId, seriesA, seriesB, labelA, labelB);
    }), w = vb.width, h = vb.height;
    var padT = 10, padB = 24;
    var n = seriesA.length;
    var valuesA = seriesA.map(function (d) { return d.headcount; });
    var valuesB = seriesB.map(function (d) { return d.headcount; });
    var max = Math.max.apply(null, valuesA.concat(valuesB)) || 1;
    var sy = function (v) { return h - padB - (v / max) * (h - padT - padB); };
    var base = h - padB;
    var groupW = w / n;
    var barW = groupW * 0.32;
    var gap = groupW * 0.06;
    var accent = cssVar("--accent");
    var secondary = "#3f7fb8";
    var mute = cssVar("--mute") || "#5f6b7a";
    var bars = "", labels = "";
    for (var i = 0; i < n; i++) {
      var groupX = i * groupW;
      var xA = groupX + groupW / 2 - gap / 2 - barW;
      var xB = groupX + groupW / 2 + gap / 2;
      var yA = sy(valuesA[i]), yB = sy(valuesB[i]);
      bars += '<rect x="' + xA.toFixed(1) + '" y="' + yA.toFixed(1) + '" width="' + barW.toFixed(1) +
        '" height="' + (base - yA).toFixed(1) + '" fill="' + accent + '" rx="1.5"/>';
      bars += '<rect x="' + xB.toFixed(1) + '" y="' + yB.toFixed(1) + '" width="' + barW.toFixed(1) +
        '" height="' + (base - yB).toFixed(1) + '" fill="' + secondary + '" rx="1.5"/>';
      labels += '<text x="' + (groupX + groupW / 2).toFixed(1) + '" y="' + (h - 8) + '" font-size="11" fill="' +
        mute + '" font-family="JetBrains Mono, monospace" text-anchor="middle">' + seriesA[i].year + '</text>';
    }
    svg.innerHTML = bars + labels;
    var legend = document.getElementById(legendId);
    if (legend) {
      legend.innerHTML =
        '<span><span class="sw" style="background:' + accent + ';"></span>' + labelA + ' (' + valuesA[valuesA.length - 1].toLocaleString() + ')</span>' +
        '<span><span class="sw" style="background:' + secondary + ';"></span>' + labelB + ' (' + valuesB[valuesB.length - 1].toLocaleString() + ')</span>';
    }
  };

  window.renderDonutChart = function (svgId, legendId, items) {
    var svg = document.getElementById(svgId);
    var legend = document.getElementById(legendId);
    if (!svg || !items || !items.length) return;
    var total = items.reduce(function (a, s) { return a + s.value; }, 0);
    var r = 15.9, cx = 21, cy = 21;
    var circumference = 2 * Math.PI * r;
    var offset = 0;
    var segs = "";
    items.forEach(function (s, i) {
      var frac = total ? s.value / total : 0;
      var len = frac * circumference;
      var color = DONUT_COLORS[i % DONUT_COLORS.length];
      segs += '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="' + color +
        '" stroke-width="7" stroke-dasharray="' + len.toFixed(2) + ' ' + (circumference - len).toFixed(2) +
        '" stroke-dashoffset="' + (-offset).toFixed(2) + '" transform="rotate(-90 ' + cx + ' ' + cy + ')"/>';
      offset += len;
    });
    svg.innerHTML = segs;
    if (legend) {
      legend.innerHTML = items.map(function (s, i) {
        var pct = total ? (s.value / total * 100).toFixed(0) : "0";
        var valueText = s.label ? (s.label + ' · ' + pct + '%') : (pct + '%');
        return '<div class="donut-row"><span class="dot" style="background:' + DONUT_COLORS[i % DONUT_COLORS.length] +
          '"></span><span class="n">' + s.name + '</span><span class="v mono">' + valueText + '</span></div>';
      }).join("");
    }
  };
})();
