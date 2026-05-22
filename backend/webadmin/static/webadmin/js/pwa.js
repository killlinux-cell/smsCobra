/**
 * Enregistrement PWA + invitation à installer sur le bureau (Chrome, Edge, etc.).
 */
(function () {
  if (!("serviceWorker" in navigator)) return;

  const SW_URL = "/dashboard/service-worker.js";
  const DISMISS_KEY = "sms-pwa-install-dismissed";
  const banner = document.getElementById("pwa-install-banner");
  const installBtn = document.getElementById("pwa-install-btn");
  const dismissBtn = document.getElementById("pwa-install-dismiss");
  const manualHint = document.getElementById("pwa-install-hint-manual");

  const isStandalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;

  const isIOS =
    /iphone|ipad|ipod/i.test(navigator.userAgent) &&
    !window.MSStream;

  function hideBanner() {
    if (banner) banner.hidden = true;
  }

  function showBanner() {
    if (!banner || isStandalone) return;
    if (localStorage.getItem(DISMISS_KEY) === "1") return;
    banner.hidden = false;
    if (manualHint && (isIOS || !window.deferredPwaPrompt)) {
      manualHint.hidden = false;
    }
  }

  window.addEventListener("load", function () {
    navigator.serviceWorker
      .register(SW_URL, { scope: "/dashboard/" })
      .catch(function () {});
  });

  let deferredPrompt = null;
  window.deferredPwaPrompt = null;

  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferredPrompt = e;
    window.deferredPwaPrompt = e;
    if (manualHint) manualHint.hidden = true;
    showBanner();
  });

  if (installBtn) {
    installBtn.addEventListener("click", async function () {
      if (!deferredPrompt) {
        showBanner();
        if (manualHint) manualHint.hidden = false;
        return;
      }
      deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
      window.deferredPwaPrompt = null;
      hideBanner();
    });
  }

  if (dismissBtn) {
    dismissBtn.addEventListener("click", function () {
      localStorage.setItem(DISMISS_KEY, "1");
      hideBanner();
    });
  }

  if (!isStandalone) {
    window.setTimeout(function () {
      if (!deferredPrompt && (isIOS || banner)) showBanner();
    }, 2500);
  }
})();
