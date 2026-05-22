"""Manifeste et service worker pour l'installation PWA du dashboard."""

import json

from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

PWA_CACHE_VERSION = "1"


@require_GET
@cache_control(max_age=3600, public=True)
def manifest_view(request):
    icon_base = request.build_absolute_uri("/static/webadmin/img/")
    data = {
        "name": "SMS — Administration",
        "short_name": "SMS Admin",
        "description": "Espace d'administration Sécurité Multi Services",
        "id": "/dashboard/",
        "start_url": request.build_absolute_uri(reverse("webadmin-dashboard")),
        "scope": request.build_absolute_uri("/dashboard/"),
        "display": "standalone",
        "orientation": "any",
        "lang": "fr",
        "dir": "ltr",
        "theme_color": "#b91c1c",
        "background_color": "#141010",
        "categories": ["business", "productivity"],
        "icons": [
            {
                "src": f"{icon_base}pwa-icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": f"{icon_base}pwa-icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": f"{icon_base}pwa-icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }
    return HttpResponse(
        json.dumps(data, ensure_ascii=False),
        content_type="application/manifest+json; charset=utf-8",
    )


@require_GET
@cache_control(max_age=0, must_revalidate=True)
def service_worker_view(request):
    scope = "/dashboard/"
    cache_name = f"sms-admin-{PWA_CACHE_VERSION}"
    offline_url = request.build_absolute_uri(reverse("webadmin-dashboard"))
    body = f"""const CACHE = "{cache_name}";
const SCOPE = "{scope}";
const OFFLINE_URL = "{offline_url}";

self.addEventListener("install", (event) => {{
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.add(OFFLINE_URL).catch(() => {{}}))
  );
}});

self.addEventListener("activate", (event) => {{
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith("sms-admin-") && k !== CACHE)
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
}});

self.addEventListener("fetch", (event) => {{
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (!url.pathname.startsWith(SCOPE)) return;
  if (url.pathname.includes("/map-tiles/")) return;
  if (url.pathname.startsWith("/api/")) return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {{
        if (response.ok && response.type === "basic") {{
          const clone = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, clone));
        }}
        return response;
      }})
      .catch(() =>
        caches.match(event.request).then((cached) => cached || caches.match(OFFLINE_URL))
      )
  );
}});
"""
    return HttpResponse(body, content_type="application/javascript; charset=utf-8")
