from django import template

register = template.Library()

ASSIGNMENT_STATUS_FR = {
    "scheduled": "Planifié",
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
