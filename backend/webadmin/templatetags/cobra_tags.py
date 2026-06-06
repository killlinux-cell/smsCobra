from django import template

register = template.Library()

ASSIGNMENT_STATUS_FR = {
    "scheduled": "Planifié",
    "extra": "Extra",
    "replaced": "Remplacé",
    "completed": "Terminé",
    "missed": "Manqué",
}

ALERT_STATUS_FR = {
    "open": "Ouverte",
    "acknowledged": "Acquittée",
    "resolved": "Résolue",
}

CHECKIN_TYPE_FR = {
    "start": "Prise de service",
    "end": "Fin de service",
    "presence": "Présence (selfie horaire)",
}

ROLE_FR = {
    "super_admin": "Super administrateur",
    "admin_societe": "Administrateur société",
    "superviseur": "Superviseur",
    "controleur": "Contrôleur",
    "vigile": "Vigile",
}


@register.filter
def statut_affectation_fr(value):
    return ASSIGNMENT_STATUS_FR.get(str(value), value)


@register.filter
def statut_alerte_fr(value):
    return ALERT_STATUS_FR.get(str(value), value)


@register.filter
def alerte_kind_fr(message):
    """Libellé court du type d'alerte (préfixe du message métier)."""
    m = (message or "").strip()
    if m.startswith("Retard prise de service"):
        return "Retard prise de service"
    if m.startswith("Passation:"):
        return "Passation / relève"
    if m.startswith("Absence:"):
        return "Absence"
    if m.startswith("FinSansPointage:"):
        return "Fin non pointée"
    if m.startswith("Presence:"):
        return "Présence (ancien)"
    return "Autre"


@register.filter
def type_pointage_fr(value):
    return CHECKIN_TYPE_FR.get(str(value), value)


@register.filter
def role_fr(value):
    return ROLE_FR.get(str(value), value)


@register.simple_tag
def rapport_presence_badge(report):
    """
    Statut affiché sur le tableau de bord : exige un pointage de début pour « Présent ».
    Évite d'afficher « Présent » quand was_absent=False par défaut sans started_at.
    """
    if report.was_absent:
        return {"label": "Absent", "css": "bg-danger"}
    if report.started_at:
        if report.was_late:
            return {"label": "Retard", "css": "bg-warning text-dark"}
        if report.ended_at:
            return {"label": "Présent", "css": "bg-success"}
        return {"label": "En service", "css": "bg-info text-dark"}
    return {"label": "Non pointé", "css": "bg-secondary"}
