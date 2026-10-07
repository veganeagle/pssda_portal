// Header Sectors menu (<details class="nav-menu">): the links work without
// this file; it only closes the menu on an outside click or Escape.
(function () {
  function closeMenus(except) {
    document.querySelectorAll("details.nav-menu[open]").forEach(function (d) {
      if (d !== except) d.removeAttribute("open");
    });
  }
  document.addEventListener("click", function (e) {
    closeMenus(e.target.closest("details.nav-menu"));
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeMenus(null);
  });
})();
