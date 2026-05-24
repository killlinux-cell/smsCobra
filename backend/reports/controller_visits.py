"""Suivi des passages contrôleurs (sites visités / non visités) pour superviseurs."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from django.db.models import Prefetch
from django.utils import timezone

from accounts.models import ControllerSiteAssignment, ControllerVisit, User


def _controller_queryset(site_id: int | None = None, controller_id: int | None = None):
    qs = User.objects.filter(role=User.Role.CONTROLEUR).order_by(
        "first_name", "last_name", "username"
    )
    if controller_id:
        qs = qs.filter(pk=controller_id)
    if site_id:
        qs = qs.filter(controller_site_assignments__site_id=site_id).distinct()
    return qs.prefetch_related(
        Prefetch(
            "controller_site_assignments",
            queryset=ControllerSiteAssignment.objects.select_related("site").order_by(
                "site__name"
            ),
        )
    )


def build_controller_coverage_rows(
    presence_date: date,
    *,
    site_id: int | None = None,
    controller_id: int | None = None,
) -> list[dict]:
    """Par contrôleur : sites autorisés, visités ce jour, manquants."""
    visits_qs = ControllerVisit.objects.filter(visited_at__date=presence_date)
    if site_id:
        visits_qs = visits_qs.filter(site_id=site_id)
    if controller_id:
        visits_qs = visits_qs.filter(controller_id=controller_id)

    visits_by_controller: dict[int, list[ControllerVisit]] = defaultdict(list)
    visited_site_ids: dict[int, set[int]] = defaultdict(set)
    for visit in visits_qs.select_related("site").order_by("visited_at"):
        visits_by_controller[visit.controller_id].append(visit)
        visited_site_ids[visit.controller_id].add(visit.site_id)

    rows: list[dict] = []
    for controller in _controller_queryset(site_id=site_id, controller_id=controller_id):
        authorized = [a.site for a in controller.controller_site_assignments.all()]
        if site_id:
            authorized = [s for s in authorized if s.id == site_id]
        visited = [s for s in authorized if s.id in visited_site_ids.get(controller.id, set())]
        missing = [s for s in authorized if s.id not in visited_site_ids.get(controller.id, set())]
        day_visits = visits_by_controller.get(controller.id, [])
        rows.append(
            {
                "controller": controller,
                "authorized_sites": authorized,
                "visited_sites": visited,
                "missing_sites": missing,
                "visits_on_day": day_visits,
                "present_on_day": bool(day_visits),
                "fully_covered": bool(authorized) and not missing,
            }
        )
    return rows


def query_controller_visit_history(
    *,
    filter_day: date | None = None,
    filter_month: tuple[int, int] | None = None,
    site_id: int | None = None,
    controller_id: int | None = None,
    limit: int = 200,
) -> list[ControllerVisit]:
    qs = ControllerVisit.objects.select_related("controller", "site").order_by(
        "-visited_at"
    )
    if filter_day is not None:
        qs = qs.filter(visited_at__date=filter_day)
    elif filter_month is not None:
        y, m = filter_month
        qs = qs.filter(visited_at__year=y, visited_at__month=m)
    if site_id:
        qs = qs.filter(site_id=site_id)
    if controller_id:
        qs = qs.filter(controller_id=controller_id)
    return list(qs[: max(10, min(int(limit or 200), 500))])


def build_controller_visit_report(
    *,
    filter_day: date | None = None,
    filter_month: tuple[int, int] | None = None,
    site_id: int | None = None,
) -> dict:
    """Données pour la page Rapports (web) et l'API mobile."""
    today = timezone.localdate()
    visit_history = query_controller_visit_history(
        filter_day=filter_day,
        filter_month=filter_month if filter_day is None else None,
        site_id=site_id,
    )
    if filter_day is not None:
        coverage_date = filter_day
        show_coverage = True
    elif filter_month is None:
        coverage_date = today
        show_coverage = True
    else:
        coverage_date = None
        show_coverage = False

    coverage_rows = (
        build_controller_coverage_rows(coverage_date, site_id=site_id)
        if show_coverage and coverage_date
        else []
    )
    return {
        "visit_history": visit_history,
        "coverage_rows": coverage_rows,
        "coverage_date": coverage_date,
        "show_coverage": show_coverage,
    }


def serialize_controller_visit(visit: ControllerVisit) -> dict:
    return {
        "id": visit.id,
        "controller_id": visit.controller_id,
        "controller_name": visit.controller.display_name,
        "site_id": visit.site_id,
        "site_name": visit.site.name,
        "visited_at": visit.visited_at.isoformat() if visit.visited_at else None,
        "face_score": visit.face_score,
    }


def serialize_coverage_row(row: dict) -> dict:
    controller = row["controller"]
    return {
        "controller_id": controller.id,
        "controller_name": controller.display_name,
        "present_on_day": row["present_on_day"],
        "fully_covered": row["fully_covered"],
        "authorized_site_names": [s.name for s in row["authorized_sites"]],
        "visited_site_names": [s.name for s in row["visited_sites"]],
        "missing_site_names": [s.name for s in row["missing_sites"]],
        "visits": [
            {
                "site_name": v.site.name,
                "visited_at": v.visited_at.isoformat() if v.visited_at else None,
                "face_score": v.face_score,
            }
            for v in row["visits_on_day"]
        ],
    }
