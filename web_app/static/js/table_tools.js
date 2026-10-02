// Reusable table utilities, loaded once (base.html) and applied to every
// table on every page via data attributes — no per-table JS or server code.
//   data-collapse="5"    show only the first 5 data rows, with a show-more/
//                        show-fewer toggle (fully reversible)
//   data-csv="name.csv"  adds a "Download CSV" button that exports every
//                        row (including rows currently collapsed/hidden)
// A table with both attributes gets one shared toolbar underneath it.
(function () {
  function cellText(cell) {
    return cell.innerText.trim().replace(/\s+/g, " ");
  }

  function csvEscape(s) {
    if (/[",\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
    return s;
  }

  function tableToCsv(table) {
    var rows = table.querySelectorAll("tr");
    var lines = [];
    rows.forEach(function (row) {
      var cells = row.querySelectorAll("th,td");
      var vals = Array.prototype.map.call(cells, function (c) { return csvEscape(cellText(c)); });
      lines.push(vals.join(","));
    });
    return lines.join("\r\n");
  }

  function downloadCsv(table, filename) {
    var csv = tableToCsv(table);
    var blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = /\.csv$/i.test(filename) ? filename : filename + ".csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function toolbarFor(table) {
    var bar = table.nextElementSibling;
    if (bar && bar.classList && bar.classList.contains("table-toolbar")) return bar;
    bar = document.createElement("div");
    bar.className = "table-toolbar";
    table.insertAdjacentElement("afterend", bar);
    return bar;
  }

  function initCsvButtons() {
    document.querySelectorAll("table[data-csv]").forEach(function (table) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "csv-btn";
      btn.textContent = "Download CSV";
      btn.addEventListener("click", function () {
        downloadCsv(table, table.getAttribute("data-csv"));
      });
      toolbarFor(table).appendChild(btn);
    });
  }

  function initCollapsibleTables() {
    document.querySelectorAll("table[data-collapse]").forEach(function (table) {
      var limit = parseInt(table.getAttribute("data-collapse"), 10);
      var allRows = Array.prototype.slice.call(table.querySelectorAll("tr"));
      var bodyRows = allRows.slice(1); // first <tr> is always the header row in this app
      if (bodyRows.length <= limit) return;

      var extra = bodyRows.slice(limit);
      extra.forEach(function (r) { r.hidden = true; });

      var expanded = false;
      var toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "table-expand-btn";
      function render() {
        toggle.textContent = expanded ? "Show fewer ▴" : "Show all " + bodyRows.length + " ▾";
      }
      render();
      toggle.addEventListener("click", function () {
        expanded = !expanded;
        extra.forEach(function (r) { r.hidden = !expanded; });
        render();
      });
      toolbarFor(table).insertBefore(toggle, toolbarFor(table).firstChild);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initCsvButtons();
    initCollapsibleTables();
  });
})();
