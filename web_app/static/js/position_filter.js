// Live text-filter over the #position-select dropdown on the Top Earners page.
// Progressive enhancement only: without this script the select still works,
// just showing its full unfiltered option list. Never touches the submitted
// value's validity — filtering only hides/shows real <option> elements built
// server-side, it never invents one.
(function () {
  var filterInput = document.getElementById("position-filter");
  var select = document.getElementById("position-select");
  if (!filterInput || !select) return;

  var groups = Array.prototype.map.call(select.querySelectorAll("optgroup"), function (og) {
    return {
      label: og.label,
      options: Array.prototype.map.call(og.querySelectorAll("option"), function (opt) {
        return { value: opt.value, text: opt.textContent };
      }),
    };
  });
  var blankOption = select.querySelector('option[value=""]');

  function render(filterText) {
    var needle = filterText.trim().toLowerCase();
    var selectedValue = select.value;
    select.innerHTML = "";
    if (blankOption) select.appendChild(blankOption.cloneNode(true));

    groups.forEach(function (group) {
      var matches = group.options.filter(function (opt) {
        return opt.text.toLowerCase().indexOf(needle) !== -1;
      });
      if (matches.length === 0) return;
      var og = document.createElement("optgroup");
      og.label = group.label;
      matches.forEach(function (opt) {
        var o = document.createElement("option");
        o.value = opt.value;
        o.textContent = opt.text;
        if (opt.value === selectedValue) o.selected = true;
        og.appendChild(o);
      });
      select.appendChild(og);
    });
  }

  filterInput.addEventListener("input", function () {
    render(filterInput.value);
  });
})();
