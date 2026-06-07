"""Trace des changements de titulaire (promotion dépêche / réintégration) dans les rapports."""

from __future__ import annotations

from datetime import date

from django.utils import timezone

from reports.models import AttendanceReport, TitularChangeLog


def _guard_label(user) -> str:
    if not user:
        return "Vigile"
    return (user.get_full_name() or "").strip() or user.username


def _append_report_note(*, site_id: int, guard_id: int, report_date: date, line: str) -> None:
    if not site_id or not guard_id or not line:
        return
    report, _ = AttendanceReport.objects.get_or_create(
        site_id=site_id,
        guard_id=guard_id,
        report_date=report_date,
    )
    existing = (report.notes or "").strip()
    if line in existing:
        return
    report.notes = f"{existing}\n{line}".strip() if existing else line
    report.save(update_fields=["notes"])


def log_titular_promotion(
    *,
    fixed_post,
    assignment,
    absent_guard,
    new_titular_guard,
    actor=None,
) -> TitularChangeLog:
    """Promotion automatique du remplaçant en titulaire après dépêche."""
    ts = timezone.now()
    ts_str = timezone.localtime(ts).strftime("%d/%m/%Y %H:%M")
    site_name = fixed_post.site.name if fixed_post.site_id else "Site"
    shift_label = fixed_post.get_shift_type_display()
    absent_name = _guard_label(absent_guard)
    new_name = _guard_label(new_titular_guard)
    report_date = assignment.shift_date if assignment else timezone.localdate()

    line_absent = (
        f"[{ts_str}] Titulaire suspendu sur « {site_name} » ({shift_label}) : "
        f"{new_name} promu titulaire (dépêche absence)."
    )
    line_new = (
        f"[{ts_str}] Promu titulaire sur « {site_name} » ({shift_label}) "
        f"en remplacement de {absent_name} (dépêche)."
    )

    _append_report_note(
        site_id=fixed_post.site_id,
        guard_id=absent_guard.pk,
        report_date=report_date,
        line=line_absent,
    )
    _append_report_note(
        site_id=fixed_post.site_id,
        guard_id=new_titular_guard.pk,
        report_date=report_date,
        line=line_new,
    )

    return TitularChangeLog.objects.create(
        kind=TitularChangeLog.Kind.PROMOTED,
        site_id=fixed_post.site_id,
        fixed_post=fixed_post,
        shift_type=fixed_post.shift_type,
        from_guard=absent_guard,
        to_guard=new_titular_guard,
        assignment=assignment,
        actor=actor,
    )


def log_titular_reinstatement(
    *,
    fixed_post,
    reinstated_guard,
    former_titular_guard,
    reason: str,
    actor,
) -> TitularChangeLog:
    """Réintégration du titulaire suspendu par le superviseur."""
    ts = timezone.now()
    ts_str = timezone.localtime(ts).strftime("%d/%m/%Y %H:%M")
    site_name = fixed_post.site.name if fixed_post.site_id else "Site"
    shift_label = fixed_post.get_shift_type_display()
    reinstated_name = _guard_label(reinstated_guard)
    former_name = _guard_label(former_titular_guard)
    actor_name = _guard_label(actor)
    report_date = timezone.localdate()
    reason_short = (reason or "").strip()[:200]

    line_reinstated = (
        f"[{ts_str}] Réintégré comme titulaire sur « {site_name} » ({shift_label}) "
        f"par {actor_name}. Motif : {reason_short}"
    )
    line_former = (
        f"[{ts_str}] Fin de titularité intérimaire sur « {site_name} » ({shift_label}) : "
        f"{reinstated_name} repositionné titulaire (motif : {reason_short})."
    )

    _append_report_note(
        site_id=fixed_post.site_id,
        guard_id=reinstated_guard.pk,
        report_date=report_date,
        line=line_reinstated,
    )
    if former_titular_guard and former_titular_guard.pk != reinstated_guard.pk:
        _append_report_note(
            site_id=fixed_post.site_id,
            guard_id=former_titular_guard.pk,
            report_date=report_date,
            line=line_former,
        )

    return TitularChangeLog.objects.create(
        kind=TitularChangeLog.Kind.REINSTATED,
        site_id=fixed_post.site_id,
        fixed_post=fixed_post,
        shift_type=fixed_post.shift_type,
        from_guard=former_titular_guard,
        to_guard=reinstated_guard,
        reason=reason_short,
        actor=actor,
    )


def log_titular_retirement(
    *,
    fixed_post,
    retired_guard,
    reason: str,
    actor,
) -> TitularChangeLog:
    """Retrait volontaire d'un titulaire (réduction d'effectif, mutation, etc.)."""
    ts = timezone.now()
    ts_str = timezone.localtime(ts).strftime("%d/%m/%Y %H:%M")
    site_name = fixed_post.site.name if fixed_post.site_id else "Site"
    shift_label = fixed_post.get_shift_type_display()
    retired_name = _guard_label(retired_guard)
    actor_name = _guard_label(actor)
    report_date = timezone.localdate()
    reason_short = (reason or "").strip()[:200]

    line = (
        f"[{ts_str}] Retiré du poste titulaire sur « {site_name} » ({shift_label}) "
        f"par {actor_name}. Motif : {reason_short}"
    )
    _append_report_note(
        site_id=fixed_post.site_id,
        guard_id=retired_guard.pk,
        report_date=report_date,
        line=line,
    )

    return TitularChangeLog.objects.create(
        kind=TitularChangeLog.Kind.RETIRED,
        site_id=fixed_post.site_id,
        fixed_post=fixed_post,
        shift_type=fixed_post.shift_type,
        from_guard=retired_guard,
        to_guard=None,
        reason=reason_short,
        actor=actor,
    )
