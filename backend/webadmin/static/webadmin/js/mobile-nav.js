(function () {
  var offcanvasEl = document.getElementById("cobraMobileNav");
  if (!offcanvasEl || typeof bootstrap === "undefined") return;

  offcanvasEl.querySelectorAll("a.nav-link").forEach(function (link) {
    link.addEventListener("click", function () {
      var instance = bootstrap.Offcanvas.getInstance(offcanvasEl);
      if (instance) instance.hide();
    });
  });
})();
