import csv
import calendar
from collections import defaultdict
from urllib.parse import urlencode
from datetime import date, datetime, timedelta
from functools import wraps
from io import StringIO
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import ControllerSiteAssignment, ControllerVisit, User
from alerts.models import LateAlert
from checkins.models import Checkin
from reports.activity_feed import build_activity_events
from reports.models import AttendanceReport
from shifts.models import FixedPost, ShiftAssignment
from shifts.services import ensure_assignments_for_dates
from sites.models import Site

from alerts.firebase_init import is_firebase_initialized

from .forms import (
    AdminFcmTokenForm,
    ControllerCreationForm,
    DispatchForm,
    ShiftAssignmentForm,
    SiteForm,
    VigileCreationForm,
    VigileUpdateForm,
)
from .templatetags.cobra_tags import ASSIGNMENT_STATUS_FR

_ALERT_SCAN_CACHE_KEY = "cobra:webadmin_alert_scan"
_ALERT_SCAN_INTERVAL_SEC = 180


def _dashboard_map_payload(assignments_qs):
    """
    Marqueurs Leaflet : chaque affectation du jour (vigile au poste = coordonnées du site).
    Plusieurs vigiles sur le même site : léger décalage des marqueurs pour les distinguer.
    Cercles = périmètre géofence enregistré sur le site.
    """
    # Ne pas exclure les sites inactifs : sinon affectation visible ailleurs mais carte vide (incohérence).
    items = list(
        assignments_qs.select_related("site", "guard").order_by("site_id", "start_time")
    )
    if not items:
        return {"markers": [], "circles": []}

    by_site = defaultdict(list)
    for a in items:
        by_site[a.site_id].append(a)

    markers = []
    circles = []
    seen_circle_site = set()

    for _site_id, group in by_site.items():
        site = group[0].site
        lat0 = float(site.latitude)
        lon0 = float(site.longitude)
        if site.id not in seen_circle_site:
            seen_circle_site.add(site.id)
            r_nom = int(site.geofence_radius_meters)
            r_margin = int(site.geofence_gps_margin_meters)
            circles.append(
                {
                    "lat": lat0,
                    "lng": lon0,
                    "radius_m": r_nom,
                    "margin_m": r_margin,
                    "effective_radius_m": r_nom + r_margin,
                    "site_name": site.name,
                    "address": site.address,
                    "site_active": site.is_active,
                }
            )
        for i, a in enumerate(group):
            lat = lat0 + i * 0.00022
            lon = lon0 + i * 0.00016
            markers.append(
                {
                    "id": a.id,
                    "lat": lat,
                    "lng": lon,
                    "site_lat": lat0,
                    "site_lng": lon0,
                    "site_name": a.site.name,
                    "address": a.site.address,
                    "site_active": a.site.is_active,
                    "guard_name": a.guard.display_name,
                    "start": a.start_time.strftime("%H:%M"),
                    "end": a.end_time.strftime("%H:%M"),
                    "status": a.status,
                    "status_fr": ASSIGNMENT_STATUS_FR.get(str(a.status), a.status),
                }
            )

    return {"markers": markers, "circles": circles}


def _refresh_late_alerts_if_due() -> None:
    """
    Lance la détection retards / passation / présence sans Celery obligatoire.
    Au plus une fois toutes les _ALERT_SCAN_INTERVAL_SEC secondes par instance Django.
    """
    if not cache.add(_ALERT_SCAN_CACHE_KEY, 1, timeout=_ALERT_SCAN_INTERVAL_SEC):
        return
    try:
        from alerts.tasks import detect_missed_shift_task

        detect_missed_shift_task()
    except Exception:
        cache.delete(_ALERT_SCAN_CACHE_KEY)
        raise


def _reports_queryset(request):
    site_id = request.GET.get("site")
    report_date = request.GET.get("date")
    month_str = (request.GET.get("month") or "").strip()
    vigile_id = request.GET.get("vigile")
    qs = AttendanceReport.objects.select_related("site", "guard").order_by("-report_date", "site__name")
    if site_id and str(site_id).isdigit():
        qs = qs.filter(site_id=int(site_id))
    if vigile_id and str(vigile_id).isdigit():
        qs = qs.filter(guard_id=int(vigile_id))
    if report_date:
        qs = qs.filter(report_date=report_date)
    elif month_str:
        try:
            y_str, m_str = month_str.split("-", 1)
            qs = qs.filter(report_date__year=int(y_str), report_date__month=int(m_str))
        except (ValueError, IndexError):
            pass
    return qs


def _parse_activity_iso(iso_str: str | None) -> datetime | None:
    if not iso_str or not str(iso_str).strip():
        return None
    s = str(iso_str).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _vigile_month_bilan(guard_id: int, year: int, month: int) -> dict | None:
    """Synthèse indicative pour la paie / contrôle (non juridique)."""
    guard = User.objects.filter(id=guard_id, role=User.Role.VIGILE).first()
    if not guard:
        return None
    reports = AttendanceReport.objects.filter(
        guard_id=guard_id,
        report_date__year=year,
        report_date__month=month,
    ).select_related("site")
    n_reports = reports.count()
    n_with_start = reports.exclude(started_at__isnull=True).count()
    n_with_end = reports.exclude(ended_at__isnull=True).count()
    n_late = reports.filter(was_late=True).count()
    n_no_end = reports.filter(started_at__isnull=False, ended_at__isnull=True).count()
    n_full_day = reports.filter(
        started_at__isnull=False,
        ended_at__isnull=False,
    ).count()

    assign_qs = ShiftAssignment.objects.filter(
        guard_id=guard_id,
        shift_date__year=year,
        shift_date__month=month,
    )
    n_assign = assign_qs.count()
    n_missed = assign_qs.filter(status=ShiftAssignment.Status.MISSED).count()
    n_completed = assign_qs.filter(status=ShiftAssignment.Status.COMPLETED).count()
    n_scheduled = assign_qs.filter(status=ShiftAssignment.Status.SCHEDULED).count()
    n_replaced = assign_qs.filter(status=ShiftAssignment.Status.REPLACED).count()

    points: list[tuple[str, str]] = []
    if n_late:
        points.append(
            (
                "warning",
                f"{n_late} jour(s) avec retard enregistré à la prise de service — à qualifier avec le règlement interne.",
            )
        )
    if n_no_end:
        points.append(
            (
                "danger",
                f"{n_no_end} jour(s) avec début pointé mais sans fin de service — vérifier les heures réelles avant toute retenue sur salaire.",
            )
        )
    if n_missed:
        points.append(
            (
                "danger",
                f"{n_missed} affectation(s) marquée(s) « manquée » sur la période.",
            )
        )
    if n_assign and n_with_start < n_assign:
        delta = n_assign - n_with_start
        points.append(
            (
                "warning",
                f"{delta} affectation(s) planifiée(s) sans rapport de pointage avec début ce mois-ci (écarts à contrôler).",
            )
        )

    return {
        "guard": guard,
        "year": year,
        "month": month,
        "n_reports": n_reports,
        "n_with_start": n_with_start,
        "n_with_end": n_with_end,
        "n_full_day": n_full_day,
        "n_late": n_late,
        "n_no_end": n_no_end,
        "n_assign": n_assign,
        "n_missed": n_missed,
        "n_completed": n_completed,
        "n_scheduled": n_scheduled,
        "n_replaced": n_replaced,
        "points": points,
    }


def _checkins_queryset(request):
    qs = Checkin.objects.select_related("guard", "assignment__site").order_by("-timestamp")
    site_id = request.GET.get("site")
    day = request.GET.get("date")
    if site_id and str(site_id).isdigit():
        qs = qs.filter(assignment__site_id=int(site_id))
    if day:
        try:
            d = datetime.strptime(day, "%Y-%m-%d").date()
            qs = qs.filter(timestamp__date=d)
        except ValueError:
            pass
    return qs


def _is_admin_role(user) -> bool:
    return user.is_authenticated and getattr(user, "role", "") in {
        "super_admin",
        "admin_societe",
        "superviseur",
    }


def admin_web_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")
        if not _is_admin_role(request.user):
            return HttpResponseForbidden("Accès refusé.")
        return view_func(request, *args, **kwargs)

    return wrapper


_MAX_MAP_TILE_ZOOM = 19


def _map_tile_coords_valid(z: int, x: int, y: int) -> bool:
    if z < 0 or z > _MAX_MAP_TILE_ZOOM:
        return False
    n = 1 << z
    return 0 <= x < n and 0 <= y < n


@admin_web_required
def map_tile_proxy_view(request, z: int, x: int, y: int):
    """
    Sert les tuiles OSM en « même origine » que l’admin : le navigateur ne contacte plus
    tile.openstreetmap.* / cartocdn (souvent bloqués par proxy / pare-feu / politique réseau).
    """
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    if not _map_tile_coords_valid(z, x, y):
        return HttpResponse(status=404)

    cache_key = f"cobra:maptile:osm:{z}:{x}:{y}"
    blob = cache.get(cache_key)
    if blob is None:
        urls = (
            f"https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            f"https://a.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png",
        )
        blob = None
        for url in urls:
            try:
                req = Request(
                    url,
                    headers={
                        "User-Agent": "SMSProtection/1.0 (admin map tile proxy)",
                        "Accept": "image/png,*/*",
                    },
                )
                with urlopen(req, timeout=15) as resp:
                    blob = resp.read()
                if blob and 100 < len(blob) < 3_000_000:
                    break
            except (HTTPError, URLError, OSError, ValueError):
                blob = None
        if not blob:
            return HttpResponse("Tuile indisponible (serveur OSM injoignable).", status=502, content_type="text/plain")
        cache.set(cache_key, blob, timeout=86400)

    response = HttpResponse(blob, content_type="image/png")
    response["Cache-Control"] = "public, max-age=86400"
    return response


def login_view(request):
    if request.user.is_authenticated and _is_admin_role(request.user):
        return redirect("webadmin-dashboard")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None and _is_admin_role(user):
            login(request, user)
            nxt = request.GET.get("next") or "webadmin-dashboard"
            return redirect(nxt)
        messages.error(
            request,
            "Identifiants incorrects ou votre compte n'a pas accès à l'espace d'administration.",
        )
    return render(request, "webadmin/login.html")


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "Vous êtes déconnecté.")
    return redirect("webadmin-login")


@admin_web_required
def notifications_push_view(request):
    if request.method == "POST" and request.POST.get("action") == "clear":
        request.user.fcm_token = ""
        request.user.save(update_fields=["fcm_token"])
        messages.success(request, "Token FCM supprimé.")
        return redirect("webadmin-notifications-push")

    if request.method == "POST":
        form = AdminFcmTokenForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Token FCM enregistré. Les prochaines alertes pourront vous être envoyées sur cet appareil.",
            )
            return redirect("webadmin-notifications-push")
    else:
        form = AdminFcmTokenForm(instance=request.user)

    return render(
        request,
        "webadmin/notifications_push.html",
        {
            "page_title": "Notifications push",
            "nav_active": "notifications",
            "form": form,
            "fcm_backend_ready": is_firebase_initialized(),
        },
    )


@admin_web_required
def dashboard_view(request):
    _refresh_late_alerts_if_due()
    # Date « métier » = fuseau Django (Africa/Abidjan), pas la date OS du serveur.
    today = timezone.localdate()
    assignments = ShiftAssignment.objects.filter(shift_date=today)
    open_alerts = LateAlert.objects.filter(status=LateAlert.Status.OPEN).select_related(
        "assignment", "assignment__site", "assignment__guard"
    )
    reports = AttendanceReport.objects.select_related("site", "guard").order_by("-report_date")[:15]
    controller_visits_today = (
        ControllerVisit.objects.select_related("controller", "site")
        .filter(visited_at__date=today)
        .order_by("-visited_at")[:25]
    )
    recent_raw = (
        Checkin.objects.select_related("guard", "assignment__site").order_by("-timestamp")[:50]
    )
    recent_checkins = []
    seen_start_end = set()
    for c in recent_raw:
        # On masque les doublons START/END sur la même affectation (mais on garde toutes les PRESENCE).
        if c.type in [Checkin.Type.START, Checkin.Type.END]:
            key = (c.assignment_id, c.type)
            if key in seen_start_end:
                continue
            seen_start_end.add(key)
        recent_checkins.append(c)
        if len(recent_checkins) >= 10:
            break

    map_qs = assignments.select_related("site", "guard").order_by("site__name", "start_time")
    dashboard_map_data = _dashboard_map_payload(map_qs)

    tile_path = reverse("webadmin-map-tiles", kwargs={"z": 0, "x": 0, "y": 0})
    map_tile_url = tile_path.replace("/0/0/0.png", "/{z}/{x}/{y}.png")

    context = {
        "page_title": "Tableau de bord",
        "nav_active": "dashboard",
        "dashboard_map_data": dashboard_map_data,
        "map_tile_url": map_tile_url,
        "kpi": {
            "total": assignments.count(),
            "scheduled": assignments.filter(status=ShiftAssignment.Status.SCHEDULED).count(),
            "replaced": assignments.filter(status=ShiftAssignment.Status.REPLACED).count(),
            "completed": assignments.filter(status=ShiftAssignment.Status.COMPLETED).count(),
            "missed": assignments.filter(status=ShiftAssignment.Status.MISSED).count(),
            "open_alerts": open_alerts.count(),
            "sites": Site.objects.filter(is_active=True).count(),
            "vigiles": User.objects.filter(role=User.Role.VIGILE).count(),
            "controleurs": User.objects.filter(role=User.Role.CONTROLEUR, is_active=True).count(),
            "controller_visits_today": controller_visits_today.count(),
        },
        "alerts": open_alerts[:8],
        "reports": reports,
        "today_assignments": assignments.select_related("site", "guard").order_by("start_time")[:12],
        "recent_checkins": recent_checkins,
        "controller_visits_today": controller_visits_today,
    }
    return render(request, "webadmin/dashboard.html", context)


@admin_web_required
def sites_list_view(request):
    search_q = (request.GET.get("q") or "").strip()
    sites = Site.objects.all().order_by("name")
    if search_q:
        sites = sites.filter(Q(name__icontains=search_q) | Q(address__icontains=search_q))
    form = SiteForm()
    if request.method == "POST":
        form = SiteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Site enregistré avec succès.")
            preserve = (request.POST.get("preserve_q") or "").strip()
            if preserve:
                return redirect(f"{reverse('webadmin-sites')}?{urlencode({'q': preserve})}")
            return redirect("webadmin-sites")
    return render(
        request,
        "webadmin/sites.html",
        {
            "page_title": "Sites",
            "nav_active": "sites",
            "sites": sites,
            "form": form,
            "search_q": search_q,
        },
    )


@admin_web_required
def site_detail_view(request, pk):
    site = get_object_or_404(Site.objects.all(), pk=pk)
    today = timezone.localdate()
    date_from = today - timedelta(days=30)
    date_to = today + timedelta(days=90)

    fixed_posts = (
        FixedPost.objects.filter(site=site, is_active=True)
        .select_related("titular_guard", "replacement_guard")
        .order_by("shift_type")
    )

    assignments_qs = ShiftAssignment.objects.filter(
        site=site, shift_date__gte=date_from, shift_date__lte=date_to
    ).select_related("guard", "original_guard")
    assignments_total = assignments_qs.count()
    assignments = list(assignments_qs.order_by("shift_date", "start_time")[:250])

    def _shift_label(fp: FixedPost) -> str:
        if fp.shift_type == FixedPost.ShiftType.DAY:
            return "jour"
        if fp.shift_type == FixedPost.ShiftType.NIGHT:
            return "nuit"
        return fp.get_shift_type_display()

    guards_map: dict[int, dict] = {}

    def note_role(user, label: str) -> None:
        if user is None:
            return
        entry = guards_map.setdefault(user.id, {"user": user, "roles": set()})
        entry["roles"].add(label)

    for fp in fixed_posts:
        lab = _shift_label(fp)
        note_role(fp.titular_guard, f"Titulaire — {lab}")
        if fp.replacement_guard_id:
            if fp.replacement_active:
                note_role(fp.replacement_guard, f"Remplaçant en poste — {lab}")
            else:
                note_role(fp.replacement_guard, f"Remplaçant désigné — {lab}")

    status_counters: dict[int, dict[str, int]] = defaultdict(
        lambda: {"planifie": 0, "termine": 0, "manque": 0, "remplace_statut": 0}
    )
    guard_ids_seen: set[int] = set(guards_map.keys())

    for a in assignments_qs.iterator(chunk_size=200):
        guard_ids_seen.add(a.guard_id)
        bucket = status_counters[a.guard_id]
        if a.status == ShiftAssignment.Status.SCHEDULED:
            bucket["planifie"] += 1
        elif a.status == ShiftAssignment.Status.COMPLETED:
            bucket["termine"] += 1
        elif a.status == ShiftAssignment.Status.MISSED:
            bucket["manque"] += 1
        elif a.status == ShiftAssignment.Status.REPLACED:
            bucket["remplace_statut"] += 1

    attendance_by_guard: dict[int, dict[str, int]] = defaultdict(lambda: {"pointes": 0, "retards": 0})
    for r in AttendanceReport.objects.filter(
        site=site,
        report_date__gte=date_from,
        report_date__lte=date_to,
    ).only("guard_id", "started_at", "was_late"):
        guard_ids_seen.add(r.guard_id)
        if r.started_at is not None:
            attendance_by_guard[r.guard_id]["pointes"] += 1
        if r.was_late:
            attendance_by_guard[r.guard_id]["retards"] += 1

    users_by_id = {
        u.id: u
        for u in User.objects.filter(id__in=guard_ids_seen).only(
            "id", "username", "first_name", "last_name", "email"
        )
    }

    guard_rows = []
    for uid in sorted(
        guard_ids_seen,
        key=lambda i: (users_by_id.get(i).get_full_name() or users_by_id.get(i).username).lower()
        if users_by_id.get(i)
        else "",
    ):
        u = users_by_id.get(uid)
        if u is None:
            continue
        roles = sorted(guards_map.get(uid, {}).get("roles", []))
        c = status_counters.get(
            uid, {"planifie": 0, "termine": 0, "manque": 0, "remplace_statut": 0}
        )
        att = attendance_by_guard.get(uid, {"pointes": 0, "retards": 0})
        guard_rows.append(
            {
                "user": u,
                "roles": roles,
                "planifie": c["planifie"],
                "termine": c["termine"],
                "manque": c["manque"],
                "remplace_statut": c["remplace_statut"],
                "pointes": att["pointes"],
                "retards": att["retards"],
            }
        )

    return render(
        request,
        "webadmin/site_detail.html",
        {
            "page_title": site.name,
            "nav_active": "sites",
            "site": site,
            "fixed_posts": fixed_posts,
            "assignments": assignments,
            "assignments_total": assignments_total,
            "guard_rows": guard_rows,
            "assignments_date_from": date_from,
            "assignments_date_to": date_to,
        },
    )


@admin_web_required
def site_edit_view(request, pk):
    site = get_object_or_404(Site, pk=pk)
    if request.method == "POST":
        form = SiteForm(request.POST, instance=site)
        if form.is_valid():
            form.save()
            messages.success(request, "Site mis à jour.")
            return redirect("webadmin-sites")
    else:
        form = SiteForm(instance=site)
    return render(
        request,
        "webadmin/site_form.html",
        {
            "page_title": f"Modifier — {site.name}",
            "nav_active": "sites",
            "form": form,
            "site": site,
        },
    )


@admin_web_required
def site_delete_view(request, pk):
    site = get_object_or_404(Site, pk=pk)
    if request.method == "POST":
        name = site.name
        site.delete()
        messages.success(request, f"Le site « {name} » a été supprimé.")
        return redirect("webadmin-sites")
    return render(
        request,
        "webadmin/site_confirm_delete.html",
        {"page_title": "Supprimer un site", "nav_active": "sites", "site": site},
    )


@admin_web_required
def vigiles_list_view(request):
    vigiles = User.objects.filter(role=User.Role.VIGILE).order_by("username")
    search_q = (request.GET.get("q") or "").strip()
    if search_q:
        vigiles = vigiles.filter(
            Q(username__icontains=search_q)
            | Q(first_name__icontains=search_q)
            | Q(last_name__icontains=search_q)
            | Q(email__icontains=search_q)
            | Q(phone_number__icontains=search_q)
            | Q(domicile__icontains=search_q)
            | Q(aval__icontains=search_q)
        )
    form = VigileCreationForm()
    if request.method == "POST":
        form = VigileCreationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Vigile créé. Il peut désormais pointer via reconnaissance faciale.")
            if search_q:
                return redirect(f"{reverse('webadmin-vigiles')}?{urlencode({'q': search_q})}")
            return redirect("webadmin-vigiles")
    return render(
        request,
        "webadmin/vigiles.html",
        {
            "page_title": "Vigiles",
            "nav_active": "vigiles",
            "vigiles": vigiles,
            "search_q": search_q,
            "form": form,
        },
    )


@admin_web_required
def controllers_list_view(request):
    controllers = (
        User.objects.filter(role=User.Role.CONTROLEUR)
        .prefetch_related("controller_site_assignments__site")
        .order_by("first_name", "last_name", "username")
    )
    search_q = (request.GET.get("q") or "").strip()
    if search_q:
        controllers = controllers.filter(
            Q(username__icontains=search_q)
            | Q(first_name__icontains=search_q)
            | Q(last_name__icontains=search_q)
            | Q(email__icontains=search_q)
            | Q(phone_number__icontains=search_q)
        )

    form = ControllerCreationForm()
    if request.method == "POST":
        form = ControllerCreationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Contrôleur enregistré avec ses sites autorisés.")
            return redirect("webadmin-controllers")

    visits_by_controller = defaultdict(list)
    for visit in (
        ControllerVisit.objects.select_related("site", "controller")
        .order_by("-visited_at")[:200]
    ):
        bucket = visits_by_controller[visit.controller_id]
        if len(bucket) < 4:
            bucket.append(visit)
    controller_rows = [
        {
            "controller": c,
            "recent_visits": visits_by_controller.get(c.id, []),
        }
        for c in controllers
    ]

    return render(
        request,
        "webadmin/controllers.html",
        {
            "page_title": "Contrôleurs",
            "nav_active": "controllers",
            "controller_rows": controller_rows,
            "form": form,
            "search_q": search_q,
        },
    )


def _id_document_kind(user: User) -> str | None:
    """Pour l'affichage : aperçu image vs lien PDF."""
    if not user.id_document:
        return None
    name = user.id_document.name.lower()
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff")):
        return "image"
    return "file"


@admin_web_required
def vigile_detail_view(request, pk):
    vigile = get_object_or_404(User.objects.filter(role=User.Role.VIGILE), pk=pk)
    list_qs = request.GET.urlencode()
    if request.method == "POST":
        form = VigileUpdateForm(request.POST, request.FILES, instance=vigile)
        if form.is_valid():
            form.save()
            messages.success(request, "Fiche du vigile mise à jour.")
            redir = reverse("webadmin-vigile-detail", args=[pk])
            if list_qs:
                redir = f"{redir}?{list_qs}"
            return redirect(redir)
    else:
        form = VigileUpdateForm(instance=vigile)
    return render(
        request,
        "webadmin/vigile_detail.html",
        {
            "page_title": f"Vigile — {vigile.username}",
            "nav_active": "vigiles",
            "vigile": vigile,
            "form": form,
            "id_document_kind": _id_document_kind(vigile),
            "vigiles_list_querystring": list_qs,
        },
    )


@admin_web_required
def affectations_list_view(request):
    today = timezone.localdate()
    horizon_days = [today + timedelta(days=i) for i in range(31)]
    ensure_assignments_for_dates(horizon_days)

    site_raw = (request.GET.get("site") or "").strip()
    filter_site_pk = int(site_raw) if site_raw.isdigit() else None

    qs = ShiftAssignment.objects.select_related("site", "guard", "original_guard").order_by(
        "-shift_date", "start_time"
    )
    filter_site = None
    if filter_site_pk:
        qs = qs.filter(site_id=filter_site_pk)
        filter_site = Site.objects.filter(pk=filter_site_pk).first()
    form = ShiftAssignmentForm()
    dispatch_form = DispatchForm(
        assignments_qs=ShiftAssignment.objects.select_related("site", "guard", "original_guard")
        .filter(shift_date=today)
        .order_by("site__name", "start_time"),
    )
    if request.method == "POST":
        form = ShiftAssignmentForm(request.POST)
        if form.is_valid():
            obj = form.save()
            ensure_assignments_for_dates(horizon_days)
            messages.success(
                request,
                (
                    "Affectation créée comme poste titulaire quotidien "
                    "(reconduction automatique active)."
                ),
            )
            return redirect("webadmin-affectations")
    return render(
        request,
        "webadmin/affectations.html",
        {
            "page_title": "Affectations",
            "nav_active": "affectations",
            "assignments": qs[:200],
            "form": form,
            "dispatch_form": dispatch_form,
            "today": today,
            "filter_site": filter_site,
            "filter_site_pk": filter_site_pk,
        },
    )


@admin_web_required
def affectations_titulaires_view(request):
    today = timezone.localdate()
    horizon_days = [today + timedelta(days=i) for i in range(31)]
    ensure_assignments_for_dates(horizon_days)
    sites = list(Site.objects.filter(is_active=True).order_by("name"))
    fixed_posts = (
        FixedPost.objects.select_related("site", "titular_guard", "replacement_guard")
        .filter(is_active=True, site__in=sites)
        .order_by("site__name", "shift_type")
    )
    fixed_by_site_shift = {(fp.site_id, fp.shift_type): fp for fp in fixed_posts}
    today_assignments = (
        ShiftAssignment.objects.select_related("guard")
        .filter(shift_date=today, site__in=sites)
        .order_by("site__name", "start_time")
    )
    today_by_site_shift = {}
    for assignment in today_assignments:
        shift_type = "day" if assignment.start_time.strftime("%H:%M") == "06:00" else "night"
        today_by_site_shift[(assignment.site_id, shift_type)] = assignment

    rows = []
    for site in sites:
        day_fixed = fixed_by_site_shift.get((site.id, FixedPost.ShiftType.DAY))
        night_fixed = fixed_by_site_shift.get((site.id, FixedPost.ShiftType.NIGHT))
        day_today = today_by_site_shift.get((site.id, "day"))
        night_today = today_by_site_shift.get((site.id, "night"))
        rows.append(
            {
                "site": site,
                "day_fixed": day_fixed,
                "night_fixed": night_fixed,
                "day_today": day_today,
                "night_today": night_today,
            }
        )

    return render(
        request,
        "webadmin/affectations_titulaires.html",
        {
            "page_title": "Titulaires par site",
            "nav_active": "affectations",
            "rows": rows,
            "today": today,
        },
    )


@admin_web_required
def affectation_edit_view(request, pk):
    obj = get_object_or_404(ShiftAssignment, pk=pk)
    if request.method == "POST":
        form = ShiftAssignmentForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Affectation mise à jour.")
            return redirect("webadmin-affectations")
    else:
        form = ShiftAssignmentForm(instance=obj)
    return render(
        request,
        "webadmin/affectation_form.html",
        {
            "page_title": "Modifier une affectation",
            "nav_active": "affectations",
            "form": form,
            "assignment": obj,
        },
    )


@admin_web_required
def affectation_delete_view(request, pk):
    obj = get_object_or_404(ShiftAssignment, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Affectation supprimée.")
        return redirect("webadmin-affectations")
    return render(
        request,
        "webadmin/affectation_confirm_delete.html",
        {
            "page_title": "Supprimer une affectation",
            "nav_active": "affectations",
            "assignment": obj,
        },
    )


@admin_web_required
def alertes_view(request):
    _refresh_late_alerts_if_due()
    day_raw = (request.GET.get("date") or "").strip()
    if day_raw:
        try:
            filter_day = datetime.strptime(day_raw, "%Y-%m-%d").date()
        except ValueError:
            filter_day = timezone.localdate()
    else:
        filter_day = timezone.localdate()
    day_alerts_qs = LateAlert.objects.filter(triggered_at__date=filter_day)
    open_count = day_alerts_qs.filter(status=LateAlert.Status.OPEN).count()
    alerts = (
        day_alerts_qs.select_related(
            "assignment", "assignment__site", "assignment__guard", "admin_recipient"
        )
        .order_by("-triggered_at")[:500]
    )

    day_assignments = list(
        ShiftAssignment.objects.select_related("site", "guard", "original_guard")
        .filter(
            shift_date=filter_day,
            status__in=[ShiftAssignment.Status.SCHEDULED, ShiftAssignment.Status.REPLACED],
        )
        .order_by("site__name", "start_time")
    )
    started_assignment_ids = set(
        Checkin.objects.filter(
            assignment_id__in=[a.id for a in day_assignments],
            type=Checkin.Type.START,
        ).values_list("assignment_id", flat=True)
    )
    now = timezone.now()
    replacement_done = [a for a in day_assignments if a.status == ShiftAssignment.Status.REPLACED]
    replacement_needed = []
    for assignment in day_assignments:
        if assignment.id in started_assignment_ids:
            continue
        tz = ZoneInfo(assignment.site.timezone or "UTC")
        deadline = datetime.combine(
            assignment.shift_date,
            assignment.start_time,
            tzinfo=tz,
        ) + timedelta(minutes=assignment.site.late_tolerance_minutes)
        if now <= deadline:
            continue
        minutes_overdue = int((now - deadline).total_seconds() // 60)
        replacement_needed.append(
            {
                "assignment": assignment,
                "deadline": deadline,
                "minutes_overdue": max(minutes_overdue, 0),
            }
        )

    return render(
        request,
        "webadmin/alertes.html",
        {
            "page_title": "Alertes",
            "nav_active": "alertes",
            "alerts": alerts,
            "filter_day": filter_day,
            "alerts_open_count": open_count,
            "replacement_done": replacement_done,
            "replacement_needed": replacement_needed,
        },
    )


@admin_web_required
def rapports_view(request):
    qs = _reports_queryset(request)
    site_id = request.GET.get("site")
    report_date = request.GET.get("date")
    month_str = (request.GET.get("month") or "").strip()
    vigile_id = request.GET.get("vigile")
    filter_site_pk = int(site_id) if site_id and str(site_id).isdigit() else None
    filter_vigile_pk = int(vigile_id) if vigile_id and str(vigile_id).isdigit() else None

    bilan = None
    if filter_vigile_pk and month_str:
        try:
            y_str, m_str = month_str.split("-", 1)
            bilan = _vigile_month_bilan(filter_vigile_pk, int(y_str), int(m_str))
        except (ValueError, IndexError):
            bilan = None

    raw_activity = build_activity_events(limit=150, site_id=filter_site_pk)
    activity_rows = [{**e, "occurred_dt": _parse_activity_iso(e.get("occurred_at"))} for e in raw_activity]
    filter_day = None
    filter_month_tuple = None
    if report_date:
        try:
            filter_day = datetime.strptime(report_date, "%Y-%m-%d").date()
        except ValueError:
            filter_day = None
    elif month_str:
        try:
            y_str, m_str = month_str.split("-", 1)
            filter_month_tuple = (int(y_str), int(m_str))
        except (ValueError, IndexError):
            filter_month_tuple = None
    if filter_day is not None:
        activity_rows = [
            row
            for row in activity_rows
            if row.get("occurred_dt") and row["occurred_dt"].date() == filter_day
        ]
    elif filter_month_tuple is not None:
        y, m = filter_month_tuple
        activity_rows = [
            row
            for row in activity_rows
            if row.get("occurred_dt")
            and row["occurred_dt"].year == y
            and row["occurred_dt"].month == m
        ]

    return render(
        request,
        "webadmin/rapports.html",
        {
            "page_title": "Rapports & journal d'activité",
            "nav_active": "rapports",
            "activity_rows": activity_rows,
            "reports": qs[:500],
            "sites": Site.objects.order_by("name"),
            "vigiles": User.objects.filter(role=User.Role.VIGILE)
            .order_by("first_name", "last_name", "username"),
            "filter_site": filter_site_pk,
            "filter_vigile": filter_vigile_pk,
            "filter_date": report_date or "",
            "filter_month": month_str,
            "bilan": bilan,
            "export_querystring": request.GET.urlencode(),
        },
    )


@admin_web_required
def export_reports_csv_view(request):
    qs = _reports_queryset(request)[:10000]
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "date_rapport",
            "site",
            "vigile",
            "debut",
            "fin",
            "retard",
            "notes",
        ]
    )
    for r in qs:
        writer.writerow(
            [
                r.id,
                r.report_date.isoformat(),
                r.site.name,
                r.guard.get_username(),
                r.started_at.isoformat() if r.started_at else "",
                r.ended_at.isoformat() if r.ended_at else "",
                "oui" if r.was_late else "non",
                (r.notes or "").replace("\n", " ").replace("\r", " ")[:500],
            ]
        )
    response = HttpResponse("\ufeff" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
    fname = timezone.now().strftime("rapports_%Y%m%d_%H%M.csv")
    response["Content-Disposition"] = f'attachment; filename="{fname}"'
    return response


@admin_web_required
def pointages_view(request):
    month_raw = (request.GET.get("month") or "").strip()
    guard_raw = (request.GET.get("guard") or "").strip()
    search_q = (request.GET.get("q") or "").strip()
    page_raw = (request.GET.get("page") or "1").strip()
    today = timezone.localdate()
    if month_raw:
        try:
            month_start = datetime.strptime(f"{month_raw}-01", "%Y-%m-%d").date()
        except ValueError:
            month_start = date(today.year, today.month, 1)
    else:
        month_start = date(today.year, today.month, 1)
    days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]
    month_end = date(month_start.year, month_start.month, days_in_month)

    vigiles_qs = User.objects.filter(role=User.Role.VIGILE).order_by(
        "first_name", "last_name", "username"
    )
    if search_q:
        vigiles_qs = vigiles_qs.filter(
            Q(username__icontains=search_q)
            | Q(first_name__icontains=search_q)
            | Q(last_name__icontains=search_q)
            | Q(email__icontains=search_q)
            | Q(phone_number__icontains=search_q)
        )
    vigiles_by_id = {u.id: u for u in vigiles_qs}
    scheduled_days_by_guard = defaultdict(set)
    site_counts_by_guard = defaultdict(lambda: defaultdict(int))

    month_assignments = ShiftAssignment.objects.select_related(
        "guard", "site", "original_guard"
    ).filter(shift_date__range=(month_start, month_end))
    for assignment in month_assignments:
        titular_id = assignment.original_guard_id or assignment.guard_id
        scheduled_days_by_guard[titular_id].add(assignment.shift_date)
        site_counts_by_guard[titular_id][assignment.site.name] += 1

    present_days_by_guard = defaultdict(set)
    month_reports = AttendanceReport.objects.filter(
        report_date__range=(month_start, month_end),
        started_at__isnull=False,
    ).only("guard_id", "report_date")
    for report in month_reports:
        present_days_by_guard[report.guard_id].add(report.report_date)

    paginator = Paginator(vigiles_qs, 24)
    page_obj = paginator.get_page(page_raw)
    summary_rows = []
    for guard in page_obj.object_list:
        scheduled_days = scheduled_days_by_guard.get(guard.id, set())
        present_days = present_days_by_guard.get(guard.id, set())
        absent_days = scheduled_days - present_days
        site_counts = site_counts_by_guard.get(guard.id, {})
        titular_site = max(site_counts, key=site_counts.get) if site_counts else "—"
        summary_rows.append(
            {
                "guard": guard,
                "titular_site": titular_site,
                "scheduled_count": len(scheduled_days),
                "present_count": len(present_days),
                "absent_count": len(absent_days),
            }
        )

    selected_guard = None
    selected_calendar_days = []
    if guard_raw.isdigit():
        selected_guard = vigiles_by_id.get(int(guard_raw))
    if selected_guard:
        scheduled_days = scheduled_days_by_guard.get(selected_guard.id, set())
        present_days = present_days_by_guard.get(selected_guard.id, set())
        for day in range(1, days_in_month + 1):
            d = date(month_start.year, month_start.month, day)
            if d in present_days:
                status = "present"
            elif d in scheduled_days:
                status = "absent"
            else:
                status = "off"
            selected_calendar_days.append({"date": d, "status": status})

    return render(
        request,
        "webadmin/pointages.html",
        {
            "page_title": "Pointages",
            "nav_active": "pointages",
            "month_start": month_start,
            "month_value": month_start.strftime("%Y-%m"),
            "days_in_month": days_in_month,
            "summary_rows": summary_rows,
            "selected_guard": selected_guard,
            "selected_calendar_days": selected_calendar_days,
            "search_q": search_q,
            "page_obj": page_obj,
            "total_vigiles": paginator.count,
        },
    )


@admin_web_required
def export_pointages_csv_view(request):
    raw_qs = _checkins_queryset(request)[:15000]
    qs = []
    seen_start_end = set()
    for c in raw_qs:
        if c.type in [Checkin.Type.START, Checkin.Type.END]:
            key = (c.assignment_id, c.type)
            if key in seen_start_end:
                continue
            seen_start_end.add(key)
        qs.append(c)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "horodatage",
            "type",
            "vigile",
            "site",
            "affectation_id",
            "dans_geofence",
            "distance_site_m",
            "latitude",
            "longitude",
        ]
    )
    for c in qs:
        writer.writerow(
            [
                c.id,
                c.timestamp.isoformat(),
                c.type,
                c.guard.get_username(),
                c.assignment.site.name,
                c.assignment_id,
                "oui" if c.within_geofence else "non",
                "" if c.distance_from_site_meters is None else round(c.distance_from_site_meters, 1),
                str(c.latitude),
                str(c.longitude),
            ]
        )
    response = HttpResponse("\ufeff" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
    fname = timezone.now().strftime("pointages_%Y%m%d_%H%M.csv")
    response["Content-Disposition"] = f'attachment; filename="{fname}"'
    return response


@admin_web_required
def ack_alert_view(request, alert_id: int):
    if request.method != "POST":
        return redirect("webadmin-alertes")
    alert = get_object_or_404(LateAlert, id=alert_id)
    alert.status = LateAlert.Status.ACKNOWLEDGED
    alert.acknowledged_at = timezone.now()
    alert.admin_recipient = request.user
    alert.save(update_fields=["status", "acknowledged_at", "admin_recipient"])
    messages.success(request, f"Alerte n°{alert.id} acquittée.")
    return redirect(request.POST.get("next") or "webadmin-alertes")


@admin_web_required
def dispatch_view(request):
    if request.method != "POST":
        return redirect("webadmin-affectations")
    today = timezone.localdate()
    form = DispatchForm(
        request.POST,
        assignments_qs=ShiftAssignment.objects.filter(shift_date=today).select_related(
            "site", "guard", "original_guard"
        ),
    )
    if not form.is_valid():
        for err in form.errors.values():
            for e in err:
                messages.error(request, e)
        return redirect(request.POST.get("next") or "webadmin-affectations")

    assignment = form.cleaned_data["assignment"]
    replacement = form.cleaned_data["replacement_guard"]
    if assignment.shift_date != today:
        messages.error(request, "Seules les affectations du jour peuvent être modifiées par dépêche.")
        return redirect(request.POST.get("next") or "webadmin-affectations")
    if replacement.pk == assignment.guard_id:
        messages.error(request, "Choisissez un autre vigile que celui déjà affecté.")
        return redirect(request.POST.get("next") or "webadmin-affectations")

    from alerts.services import notify_dispatch_replacement

    previous_name = assignment.guard.display_name
    update_fields = ["guard", "status"]
    if assignment.original_guard_id is None:
        assignment.original_guard_id = assignment.guard_id
        update_fields.append("original_guard_id")
    assignment.guard = replacement
    assignment.status = ShiftAssignment.Status.REPLACED
    assignment.updated_at = timezone.now()
    update_fields.append("updated_at")
    assignment.save(update_fields=update_fields)
    notify_dispatch_replacement(assignment, previous_name)
    messages.success(
        request,
        f"Dépêche enregistrée : {replacement.get_username()} est en poste (titulaire d'origine : {previous_name}).",
    )
    return redirect(request.POST.get("next") or "webadmin-affectations")
