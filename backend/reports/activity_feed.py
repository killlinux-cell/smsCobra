"""Journal d'activité opérationnelle pour l'app admin (sites, vigiles, affectations, dépêches, postes fixes)."""

from __future__ import annotations

from datetime import datetime

from django.db.models import F
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdminRole
from shifts.models import FixedPost, ShiftAssignment
from sites.models import Site


def _fmt_time(t) -> str:
    if t is None:
        return ""
    if hasattr(t, "strftime"):
        return t.strftime("%H:%M")
    return str(t)


def _fmt_date(d) -> str:
    if d is None:
        return ""
    if hasattr(d, "strftime"):
        return d.strftime("%d/%m/%Y")
    return str(d)


def _user_label(first: str, last: str, username: str) -> str:
    fn = (first or "").strip()
    ln = (last or "").strip()
    full = f"{fn} {ln}".strip()
    return full or (username or "Vigile")


def _event_matches_site(payload: dict, site_id: int | None) -> bool:
    if site_id is None:
        return True
    if payload.get("kind") == "vigile_created":
        return False
    sid = payload.get("site_id")
    return sid is not None and int(sid) == int(site_id)


def build_activity_events(limit: int = 50, site_id: int | None = None) -> list[dict]:
    """Fusionne plusieurs sources et renvoie une liste triée par date décroissante.

    Si ``site_id`` est renseigné, ne garde que les événements liés à ce site
    (nouveau site, affectations, remplacements, postes fixes). Les entrées
    « nouveau vigile » sont exclues de ce filtre.
    """
    limit = max(10, min(int(limit or 50), 200))
    per_bucket = min(120, max(limit * 3, limit))
    events: list[tuple[datetime, dict]] = []

    for site in (
        Site.objects.exclude(created_at__isnull=True)
        .order_by("-created_at")[:per_bucket]
    ):
        if site.created_at is None:
            continue
        events.append(
            (
                site.created_at,
                {
                    "kind": "site_created",
                    "occurred_at": site.created_at,
                    "title": "Nouveau site",
                    "body": f"{site.name} — {site.address}",
                    "site_id": site.id,
                    "site_name": site.name,
                },
            )
        )

    for user in (
        User.objects.filter(role=User.Role.VIGILE)
        .order_by("-date_joined")[:per_bucket]
    ):
        if user.date_joined is None:
            continue
        events.append(
            (
                user.date_joined,
                {
                    "kind": "vigile_created",
                    "occurred_at": user.date_joined,
                    "title": "Nouveau vigile",
                    "body": f"{user.display_name} ajouté au personnel.",
                    "user_id": user.id,
                },
            )
        )

    qs_assign = (
        ShiftAssignment.objects.select_related("site", "guard")
        .order_by("-created_at")
        .values(
            "id",
            "site_id",
            "created_at",
            "shift_date",
            "start_time",
            "end_time",
            "site__name",
            "guard__username",
            "guard__first_name",
            "guard__last_name",
        )[:per_bucket]
    )
    for row in qs_assign:
        created_at = row["created_at"]
        if created_at is None:
            continue
        guard_label = _user_label(
            row.get("guard__first_name") or "",
            row.get("guard__last_name") or "",
            row.get("guard__username") or "",
        )
        site_name = row.get("site__name") or "Site"
        sd = row["shift_date"]
        st = row["start_time"]
        et = row["end_time"]
        events.append(
            (
                created_at,
                {
                    "kind": "assignment_planned",
                    "occurred_at": created_at,
                    "title": "Affectation planifiée",
                    "body": (
                        f"{guard_label} sur « {site_name} », le {_fmt_date(sd)} "
                        f"({_fmt_time(st)} – {_fmt_time(et)})."
                    ),
                    "assignment_id": row["id"],
                    "site_id": row.get("site_id"),
                    "site_name": site_name,
                },
            )
        )

    qs_repl = (
        ShiftAssignment.objects.filter(
            status=ShiftAssignment.Status.REPLACED,
            original_guard_id__isnull=False,
        )
        .exclude(original_guard_id=F("guard_id"))
        .select_related("site", "guard", "original_guard")
        .order_by("-updated_at")[:per_bucket]
    )
    for a in qs_repl:
        if a.updated_at is None:
            continue
        orig = a.original_guard
        rep = a.guard
        orig_l = orig.display_name if orig else "Titulaire"
        rep_l = rep.display_name if rep else "Remplaçant"
        site_name = a.site.name if a.site_id else "Site"
        events.append(
            (
                a.updated_at,
                {
                    "kind": "guard_replaced",
                    "occurred_at": a.updated_at,
                    "title": "Remplacement de vigile",
                    "body": (
                        f"Sur « {site_name} », le {_fmt_date(a.shift_date)} "
                        f"({_fmt_time(a.start_time)} – {_fmt_time(a.end_time)}) : "
                        f"{orig_l} remplacé par {rep_l}."
                    ),
                    "assignment_id": a.id,
                    "site_id": a.site_id,
                    "site_name": site_name,
                },
            )
        )

    qs_fp = (
        FixedPost.objects.select_related("site", "titular_guard", "replacement_guard")
        .order_by("-created_at")[:per_bucket]
    )
    for fp in qs_fp:
        if fp.created_at is None:
            continue
        st_label = fp.get_shift_type_display()
        site_name = fp.site.name if fp.site_id else "Site"
        tit = fp.titular_guard.display_name if fp.titular_guard_id else ""
        extra = ""
        if fp.replacement_active and fp.replacement_guard_id:
            extra = f" Remplaçant actif : {fp.replacement_guard.display_name}."
        events.append(
            (
                fp.created_at,
                {
                    "kind": "fixed_post_configured",
                    "occurred_at": fp.created_at,
                    "title": "Poste fixe (jour / nuit)",
                    "body": f"« {site_name} » — {st_label}. Titulaire : {tit}.{extra}",
                    "site_id": fp.site_id,
                    "site_name": site_name,
                    "fixed_post_id": fp.id,
                },
            )
        )

    events = [(dt, p) for dt, p in events if _event_matches_site(p, site_id)]
    events.sort(key=lambda x: x[0], reverse=True)
    out: list[dict] = []
    for dt, payload in events[:limit]:
        p = dict(payload)
        oc = p.pop("occurred_at")
        if isinstance(oc, datetime):
            if timezone.is_naive(oc):
                oc = timezone.make_aware(oc, timezone.get_current_timezone())
            p["occurred_at"] = oc.isoformat()
        else:
            p["occurred_at"] = None
        out.append(p)
    return out


class ActivityFeedView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        raw_limit = request.query_params.get("limit") or "60"
        try:
            limit = int(raw_limit)
        except ValueError:
            limit = 60
        site_raw = (request.query_params.get("site") or "").strip()
        site_id = int(site_raw) if site_raw.isdigit() else None
        data = build_activity_events(limit=limit, site_id=site_id)
        return Response(data)
