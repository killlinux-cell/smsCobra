import secrets
from datetime import datetime, timedelta, time

from django import forms

from accounts.models import ControllerSiteAssignment, User
from shifts.guard_conflicts import (
    conflict_error_message,
    find_assignment_conflict_on_other_site,
    find_titular_fixed_post_on_other_site,
    titular_conflict_error_message,
)
from shifts.models import FixedPost, ShiftAssignment
from sites.models import Site

_CTRL = "form-control"
_SEL = "form-select"

_EDUCATION_LEVEL_CHOICES = [("", "— Non renseigné —")] + list(User.EducationLevel.choices)

class SiteCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    """Liste de sites en cases à cocher (template dédié, lisible sur la fiche contrôleur)."""

    template_name = "webadmin/widgets/site_checkbox_select.html"
    option_template_name = "webadmin/widgets/site_checkbox_option.html"

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        option.setdefault("attrs", {})
        option["attrs"]["class"] = "form-check-input"
        return option


_SITE_CHECKBOX_WIDGET = SiteCheckboxSelectMultiple()


class AssignmentChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        slot = f"{obj.shift_date} | {obj.start_time.strftime('%H:%M')}-{obj.end_time.strftime('%H:%M')}"
        if getattr(obj, "original_guard_id", None):
            return (
                f"#{obj.id} | {obj.site.name} | {slot} | En poste : {obj.guard.display_name} "
                f"(titulaire : {obj.original_guard.display_name})"
            )
        return f"#{obj.id} | {obj.site.name} | {slot} | Titulaire : {obj.guard.display_name}"


class GuardChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.display_name


class SiteForm(forms.ModelForm):
    class Meta:
        model = Site
        fields = [
            "name",
            "address",
            "site_manager_phone",
            "timezone",
            "expected_start_time",
            "expected_end_time",
            "day_staff_required",
            "night_staff_required",
            "late_tolerance_minutes",
            "relief_late_alert_minutes",
            "latitude",
            "longitude",
            "geofence_radius_meters",
            "geofence_gps_margin_meters",
            "is_active",
        ]
        labels = {
            "name": "Nom du site",
            "address": "Adresse",
            "site_manager_phone": "Numéro du responsable du site",
            "timezone": "Fuseau horaire",
            "expected_start_time": "Heure de prise de service attendue",
            "expected_end_time": "Heure de fin de service attendue",
            "day_staff_required": "Effectif cible poste jour",
            "night_staff_required": "Effectif cible poste nuit",
            "late_tolerance_minutes": "Tolérance de retard (prise de service, minutes)",
            "relief_late_alert_minutes": (
                "Alerte releve non arrive (minutes apres heure prevue) — "
                "identique a la tolerance de retard"
            ),
            "latitude": "Latitude (optionnel)",
            "longitude": "Longitude (optionnel)",
            "geofence_radius_meters": "Rayon géofence (mètres)",
            "is_active": "Site actif",
        }
        widgets = {
            "name": forms.TextInput(attrs={"class": _CTRL}),
            "address": forms.TextInput(attrs={"class": _CTRL}),
            "site_manager_phone": forms.TextInput(
                attrs={
                    "class": _CTRL,
                    "type": "tel",
                    "placeholder": "Ex. +225 07 00 00 00 00",
                    "autocomplete": "tel",
                }
            ),
            "timezone": forms.TextInput(attrs={"class": _CTRL}),
            "expected_start_time": forms.TimeInput(attrs={"class": _CTRL, "type": "time"}),
            "expected_end_time": forms.TimeInput(attrs={"class": _CTRL, "type": "time"}),
            "day_staff_required": forms.NumberInput(attrs={"class": _CTRL, "min": "1"}),
            "night_staff_required": forms.NumberInput(attrs={"class": _CTRL, "min": "1"}),
            "late_tolerance_minutes": forms.NumberInput(
                attrs={"class": _CTRL, "id": "id_late_tolerance_minutes", "min": "0"}
            ),
            "relief_late_alert_minutes": forms.NumberInput(
                attrs={
                    "class": _CTRL,
                    "id": "id_relief_late_alert_minutes",
                    "min": "0",
                    "readonly": "readonly",
                    "tabindex": "-1",
                }
            ),
            "latitude": forms.NumberInput(attrs={"class": _CTRL, "step": "any"}),
            "longitude": forms.NumberInput(attrs={"class": _CTRL, "step": "any"}),
            "geofence_radius_meters": forms.NumberInput(attrs={"class": _CTRL}),
            "geofence_gps_margin_meters": forms.NumberInput(attrs={"class": _CTRL}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_site_manager_phone(self):
        phone = (self.cleaned_data.get("site_manager_phone") or "").strip()
        if not phone:
            raise forms.ValidationError(
                "Le numéro du responsable du site est obligatoire."
            )
        if len(phone) < 8:
            raise forms.ValidationError(
                "Saisissez un numéro valide (au moins 8 caractères)."
            )
        return phone

    def clean(self):
        cleaned = super().clean()
        late = cleaned.get("late_tolerance_minutes")
        if late is not None:
            cleaned["relief_late_alert_minutes"] = late
        lat = cleaned.get("latitude")
        lon = cleaned.get("longitude")
        if (lat is None) != (lon is None):
            raise forms.ValidationError(
                "Renseignez la latitude et la longitude ensemble, ou laissez les deux vides."
            )
        return cleaned


class VigileCreationForm(forms.ModelForm):
    first_name = forms.CharField(label="Prénom", required=False)
    last_name = forms.CharField(label="Nom", required=False)
    email = forms.EmailField(label="Courriel", required=False)
    phone_number = forms.CharField(label="Téléphone", max_length=20, required=False)
    domicile = forms.CharField(
        label="Domicile",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": _CTRL,
                "rows": 3,
                "placeholder": "Adresse complète, quartier, ville…",
            }
        ),
        help_text="Adresse ou lieu de résidence (facultatif).",
    )
    aval = forms.CharField(
        label="Aval",
        max_length=255,
        required=False,
        help_text="Référence ou mention interne (facultatif).",
    )
    date_integration = forms.DateField(
        label="Date d'intégration",
        required=False,
        widget=forms.DateInput(attrs={"class": _CTRL, "type": "date"}),
    )
    height_cm = forms.IntegerField(
        label="Taille (cm)",
        required=False,
        min_value=100,
        max_value=250,
        widget=forms.NumberInput(attrs={"class": _CTRL, "min": "100", "max": "250", "placeholder": "ex. 175"}),
        help_text="Taille en centimètres (facultatif).",
    )
    education_level = forms.ChoiceField(
        label="Niveau d'études",
        required=False,
        choices=_EDUCATION_LEVEL_CHOICES,
        widget=forms.Select(attrs={"class": _SEL}),
    )
    id_document = forms.FileField(
        label="Pièce d'identité (scan)",
        required=False,
        help_text="Numérisez avec le scanner connecté, puis choisissez le fichier (image ou PDF).",
    )
    profile_photo = forms.ImageField(
        label="Photo portrait (obligatoire)",
        required=True,
        help_text="Utilisez la webcam ci-dessus ou choisissez un fichier image.",
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone_number")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Identifiant (généré automatiquement)"
        self.fields["username"].required = False
        self.fields["username"].help_text = "Laissez vide pour génération automatique (VIR-XXX)."
        for name in (
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "domicile",
            "aval",
            "height_cm",
        ):
            if name in self.fields:
                self.fields[name].widget.attrs.setdefault("class", _CTRL)
        self.fields["profile_photo"].widget.attrs.setdefault("class", "form-control")
        self.fields["profile_photo"].widget.attrs.setdefault("accept", "image/*")
        self.fields["id_document"].widget.attrs.setdefault("class", "form-control")
        self.fields["id_document"].widget.attrs.setdefault(
            "accept", "image/*,.pdf,application/pdf"
        )

    @staticmethod
    def _generate_username() -> str:
        max_num = 0
        for value in User.objects.filter(role=User.Role.VIGILE).values_list("username", flat=True):
            if value and value.startswith("VIR-"):
                suffix = value[4:]
                if suffix.isdigit():
                    max_num = max(max_num, int(suffix))
        return f"VIR-{max_num + 1:03d}"

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("username"):
            cleaned["username"] = self._generate_username()
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.VIGILE
        user.username = self.cleaned_data["username"]
        user.phone_number = self.cleaned_data.get("phone_number", "") or ""
        user.domicile = (self.cleaned_data.get("domicile") or "").strip()
        user.aval = (self.cleaned_data.get("aval") or "").strip()
        user.date_integration = self.cleaned_data.get("date_integration")
        user.height_cm = self.cleaned_data.get("height_cm")
        user.education_level = self.cleaned_data.get("education_level") or ""
        user.profile_photo = self.cleaned_data["profile_photo"]
        doc = self.cleaned_data.get("id_document")
        if doc:
            user.id_document = doc
        # Connexion vigile orientée biométrie : mot de passe non saisi dans ce formulaire.
        user.set_password(secrets.token_urlsafe(24))
        if commit:
            user.save()
        return user


class ControllerCreationForm(forms.ModelForm):
    first_name = forms.CharField(label="Prénom", required=False)
    last_name = forms.CharField(label="Nom", required=False)
    email = forms.EmailField(label="Courriel", required=False)
    phone_number = forms.CharField(label="Téléphone", max_length=20, required=False)
    profile_photo = forms.ImageField(
        label="Photo portrait (obligatoire)",
        required=True,
        help_text="Photo de référence pour la reconnaissance faciale.",
    )
    sites = forms.ModelMultipleChoiceField(
        label="Sites autorisés",
        queryset=Site.objects.filter(is_active=True).order_by("name"),
        required=False,
        widget=_SITE_CHECKBOX_WIDGET,
        help_text="Cochez un ou plusieurs sites où ce contrôleur peut enregistrer son passage.",
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone_number")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Identifiant (généré automatiquement)"
        self.fields["username"].required = False
        self.fields["username"].help_text = "Laissez vide pour génération automatique (CTR-XXX)."
        for name in ("username", "first_name", "last_name", "email", "phone_number"):
            if name in self.fields:
                self.fields[name].widget.attrs.setdefault("class", _CTRL)
        self.fields["profile_photo"].widget.attrs.setdefault("class", "form-control")
        self.fields["profile_photo"].widget.attrs.setdefault("accept", "image/*")

    @staticmethod
    def _generate_username() -> str:
        max_num = 0
        for value in User.objects.filter(role=User.Role.CONTROLEUR).values_list("username", flat=True):
            if value and value.startswith("CTR-"):
                suffix = value[4:]
                if suffix.isdigit():
                    max_num = max(max_num, int(suffix))
        return f"CTR-{max_num + 1:03d}"

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("username"):
            cleaned["username"] = self._generate_username()
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.CONTROLEUR
        user.username = self.cleaned_data["username"]
        user.phone_number = self.cleaned_data.get("phone_number", "") or ""
        user.profile_photo = self.cleaned_data["profile_photo"]
        user.set_password(secrets.token_urlsafe(24))
        if commit:
            user.save()
            sites = self.cleaned_data.get("sites") or []
            for site in sites:
                ControllerSiteAssignment.objects.update_or_create(
                    controller=user,
                    site=site,
                    defaults={"is_active": True},
                )
        return user


class ControllerUpdateForm(forms.ModelForm):
    """Mise à jour d'un contrôleur (coordonnées, sites autorisés, photo)."""

    sites = forms.ModelMultipleChoiceField(
        label="Sites autorisés",
        queryset=Site.objects.filter(is_active=True).order_by("name"),
        required=False,
        widget=_SITE_CHECKBOX_WIDGET,
        help_text="Cochez les sites où ce contrôleur peut pointer son passage (reconnaissance faciale).",
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "profile_photo",
            "is_active",
        )
        labels = {
            "username": "Identifiant",
            "first_name": "Prénom",
            "last_name": "Nom",
            "email": "Courriel",
            "phone_number": "Téléphone",
            "profile_photo": "Photo portrait",
            "is_active": "Compte actif (peut se connecter / pointer)",
        }
        widgets = {
            "username": forms.TextInput(attrs={"class": _CTRL}),
            "first_name": forms.TextInput(attrs={"class": _CTRL}),
            "last_name": forms.TextInput(attrs={"class": _CTRL}),
            "email": forms.EmailInput(attrs={"class": _CTRL}),
            "phone_number": forms.TextInput(attrs={"class": _CTRL}),
            "profile_photo": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profile_photo"].required = False
        if self.instance and self.instance.pk:
            assigned_ids = (
                ControllerSiteAssignment.objects.filter(
                    controller=self.instance,
                    is_active=True,
                ).values_list("site_id", flat=True)
            )
            self.fields["sites"].initial = list(assigned_ids)

    def clean_username(self):
        u = (self.cleaned_data.get("username") or "").strip()
        if not u:
            raise forms.ValidationError("L'identifiant est obligatoire.")
        if User.objects.filter(username=u).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Cet identifiant est déjà utilisé.")
        return u

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.CONTROLEUR
        if commit:
            user.save()
            selected_sites = list(self.cleaned_data.get("sites") or [])
            selected_ids = {s.pk for s in selected_sites}
            for site in selected_sites:
                ControllerSiteAssignment.objects.update_or_create(
                    controller=user,
                    site=site,
                    defaults={"is_active": True},
                )
            ControllerSiteAssignment.objects.filter(controller=user).exclude(
                site_id__in=selected_ids
            ).delete()
        return user


class VigileUpdateForm(forms.ModelForm):
    """Mise à jour d'un vigile depuis le tableau de bord (fiche détail)."""

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "domicile",
            "aval",
            "date_integration",
            "height_cm",
            "education_level",
            "profile_photo",
            "id_document",
            "is_active",
            "is_active_on_duty",
        ]
        labels = {
            "username": "Identifiant",
            "first_name": "Prénom",
            "last_name": "Nom",
            "email": "Courriel",
            "phone_number": "Téléphone",
            "domicile": "Domicile",
            "aval": "Aval",
            "date_integration": "Date d'intégration",
            "height_cm": "Taille (cm)",
            "education_level": "Niveau d'études",
            "profile_photo": "Photo portrait",
            "id_document": "Pièce d'identité (scan)",
            "is_active": "Compte actif (connexion autorisée)",
            "is_active_on_duty": "Marqué en service",
        }
        widgets = {
            "username": forms.TextInput(attrs={"class": _CTRL}),
            "first_name": forms.TextInput(attrs={"class": _CTRL}),
            "last_name": forms.TextInput(attrs={"class": _CTRL}),
            "email": forms.EmailInput(attrs={"class": _CTRL}),
            "phone_number": forms.TextInput(attrs={"class": _CTRL}),
            "domicile": forms.Textarea(attrs={"class": _CTRL, "rows": 3}),
            "aval": forms.TextInput(attrs={"class": _CTRL}),
            "date_integration": forms.DateInput(attrs={"class": _CTRL, "type": "date"}),
            "height_cm": forms.NumberInput(
                attrs={"class": _CTRL, "min": "100", "max": "250", "placeholder": "ex. 175"}
            ),
            "education_level": forms.Select(attrs={"class": _SEL}),
            "profile_photo": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            ),
            "id_document": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "image/*,.pdf,application/pdf"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_active_on_duty": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profile_photo"].required = False
        self.fields["id_document"].required = False
        self.fields["education_level"].choices = _EDUCATION_LEVEL_CHOICES

    def clean_username(self):
        u = (self.cleaned_data.get("username") or "").strip()
        if not u:
            raise forms.ValidationError("L'identifiant est obligatoire.")
        if User.objects.filter(username=u).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Cet identifiant est déjà utilisé.")
        return u

    def save(self, commit=True):
        user = super().save(commit=False)
        if not user.education_level:
            user.education_level = ""
        if commit:
            user.save()
        return user


class ShiftAssignmentForm(forms.ModelForm):
    SHIFT_TYPE_DAY = "day"
    SHIFT_TYPE_NIGHT = "night"

    MODE_PLANIFIER = "planifier"
    MODE_EXTRA = "extra"

    planning_mode = forms.ChoiceField(
        choices=(
            (MODE_PLANIFIER, "Planifier"),
            (MODE_EXTRA, "Extra"),
        ),
        label="Mode",
        initial=MODE_PLANIFIER,
        widget=forms.Select(attrs={"class": _SEL, "id": "id_planning_mode"}),
        help_text=(
            "Planifier : titulaire reconduit chaque jour. "
            "Extra : vigile(s) supplémentaire(s) sur une durée limitée alors qu'un titulaire est déjà en place."
        ),
    )
    extra_days = forms.IntegerField(
        label="Nombre de jours",
        min_value=1,
        max_value=31,
        initial=5,
        required=False,
        widget=forms.NumberInput(attrs={"class": _CTRL, "id": "id_extra_days", "min": "1", "max": "31"}),
        help_text="Durée du renfort Extra sur le site (ex. 5 jours consécutifs).",
    )
    shift_type = forms.ChoiceField(
        choices=(
            (SHIFT_TYPE_DAY, "Jour (06:00 - 18:00)"),
            (SHIFT_TYPE_NIGHT, "Nuit (18:00 - 06:00 lendemain)"),
        ),
        label="Type de poste",
        widget=forms.Select(attrs={"class": _SEL}),
    )
    create_fixed_post = forms.BooleanField(
        required=False,
        initial=True,
        label="Enregistrer comme poste fixe quotidien",
        help_text=(
            "Le titulaire est reconduit automatiquement chaque jour "
            "(jour/nuit) jusqu'à désactivation."
        ),
    )

    class Meta:
        model = ShiftAssignment
        fields = ["guard", "site", "shift_date", "shift_type"]
        labels = {
            "guard": "Vigile",
            "site": "Site",
            "shift_date": "Date de début",
        }
        widgets = {
            "guard": forms.Select(attrs={"class": _SEL}),
            "site": forms.Select(attrs={"class": _SEL}),
            "shift_date": forms.DateInput(attrs={"class": _CTRL, "type": "date"}),
        }

    def __init__(self, *args, for_create=True, **kwargs):
        self.for_create = for_create
        super().__init__(*args, **kwargs)
        self.fields["guard"].queryset = User.objects.filter(role=User.Role.VIGILE).order_by("username")
        self.fields["guard"] = GuardChoiceField(
            queryset=self.fields["guard"].queryset,
            label=self.fields["guard"].label,
        )
        self.fields["guard"].widget.attrs.setdefault("class", _SEL)
        self.fields["site"].queryset = Site.objects.filter(is_active=True).order_by("name")
        if not for_create:
            for name in ("planning_mode", "extra_days", "create_fixed_post"):
                self.fields.pop(name, None)
            if self.instance and self.instance.pk:
                if self.instance.start_time == time(6, 0):
                    self.fields["shift_type"].initial = self.SHIFT_TYPE_DAY
                elif self.instance.start_time == time(18, 0):
                    self.fields["shift_type"].initial = self.SHIFT_TYPE_NIGHT
        elif self.instance and self.instance.pk:
            if self.instance.start_time == time(6, 0):
                self.fields["shift_type"].initial = self.SHIFT_TYPE_DAY
            elif self.instance.start_time == time(18, 0):
                self.fields["shift_type"].initial = self.SHIFT_TYPE_NIGHT
        else:
            self.order_fields(
                ["planning_mode", "extra_days", "guard", "site", "shift_date", "shift_type", "create_fixed_post"]
            )

    def _slot_times(self, shift_type: str) -> tuple[time, time]:
        if shift_type == self.SHIFT_TYPE_DAY:
            return time(6, 0), time(18, 0)
        return time(18, 0), time(6, 0)

    def _fixed_post_shift_type(self, shift_type: str) -> str:
        return FixedPost.ShiftType.DAY if shift_type == self.SHIFT_TYPE_DAY else FixedPost.ShiftType.NIGHT

    def clean(self):
        cleaned = super().clean()
        site = cleaned.get("site")
        guard = cleaned.get("guard")
        shift_date = cleaned.get("shift_date")
        shift_type = cleaned.get("shift_type")
        if not (site and guard and shift_date and shift_type):
            return cleaned

        start_time, end_time = self._slot_times(shift_type)
        cleaned["start_time"] = start_time
        cleaned["end_time"] = end_time

        mode = cleaned.get("planning_mode", self.MODE_PLANIFIER) if self.for_create else None
        extra_days = cleaned.get("extra_days") or 1

        if self.for_create and mode == self.MODE_EXTRA:
            if extra_days < 1 or extra_days > 31:
                raise forms.ValidationError({"extra_days": "Indiquez une durée entre 1 et 31 jours."})
            fp_shift = self._fixed_post_shift_type(shift_type)
            titular_post = FixedPost.objects.filter(
                site=site,
                shift_type=fp_shift,
                is_active=True,
            ).first()
            if not titular_post or not titular_post.titular_guard_id:
                raise forms.ValidationError(
                    "Un titulaire doit déjà être en place sur ce site (poste jour ou nuit) "
                    "avant d'ajouter un vigile Extra."
                )
            if titular_post.titular_guard_id == guard.pk:
                raise forms.ValidationError(
                    "Le vigile Extra doit être différent du titulaire actuel du poste."
                )
            for offset in range(extra_days):
                day = shift_date + timedelta(days=offset)
                if ShiftAssignment.objects.filter(
                    site=site,
                    shift_date=day,
                    start_time=start_time,
                    guard=guard,
                ).exists():
                    raise forms.ValidationError(
                        f"Ce vigile a déjà une affectation sur ce créneau le {day.strftime('%d/%m/%Y')}."
                    )
        else:
            same_slot = ShiftAssignment.objects.filter(
                site=site,
                shift_date=shift_date,
                start_time=start_time,
            )
            if self.instance.pk:
                same_slot = same_slot.exclude(pk=self.instance.pk)
            if self.for_create and mode == self.MODE_PLANIFIER:
                non_extra_count = same_slot.exclude(status=ShiftAssignment.Status.EXTRA).count()
                required = site.staff_required_for_shift(shift_type)
                if non_extra_count >= required:
                    raise forms.ValidationError(
                        (
                            f"Effectif cible atteint pour ce site ({required} poste(s) "
                            f"{'jour' if shift_type == self.SHIFT_TYPE_DAY else 'nuit'}). "
                            "Utilisez le mode Extra pour un renfort temporaire."
                        )
                    )
            elif same_slot.exists():
                raise forms.ValidationError(
                    "Ce poste (jour/nuit) est déjà attribué pour ce site et cette date."
                )

        if shift_type == self.SHIFT_TYPE_DAY:
            opposite_date = shift_date - timedelta(days=1)
            opposite_start = time(18, 0)
        else:
            opposite_date = shift_date + timedelta(days=1)
            opposite_start = time(6, 0)
        opposite = ShiftAssignment.objects.filter(
            site=site,
            shift_date=opposite_date,
            start_time=opposite_start,
            guard=guard,
        )
        if self.instance.pk:
            opposite = opposite.exclude(pk=self.instance.pk)
        if opposite.exists():
            raise forms.ValidationError(
                "Ce vigile est déjà affecté au poste opposé autour de cette passation. Choisissez un autre vigile."
            )

        exclude_pk = self.instance.pk if self.instance.pk else None
        if self.for_create and mode == self.MODE_EXTRA:
            for offset in range(extra_days):
                day = shift_date + timedelta(days=offset)
                conflict = find_assignment_conflict_on_other_site(
                    guard_id=guard.pk,
                    site_id=site.pk,
                    shift_date=day,
                    start_time=start_time,
                    exclude_assignment_id=exclude_pk,
                )
                if conflict:
                    raise forms.ValidationError(conflict_error_message(conflict))
        else:
            conflict = find_assignment_conflict_on_other_site(
                guard_id=guard.pk,
                site_id=site.pk,
                shift_date=shift_date,
                start_time=start_time,
                exclude_assignment_id=exclude_pk,
            )
            if conflict:
                raise forms.ValidationError(conflict_error_message(conflict))

        if self.for_create and mode != self.MODE_EXTRA and self.cleaned_data.get("create_fixed_post"):
            fp_shift = self._fixed_post_shift_type(shift_type)
            titular_elsewhere = find_titular_fixed_post_on_other_site(
                guard_id=guard.pk,
                site_id=site.pk,
                shift_type=fp_shift,
            )
            if titular_elsewhere:
                raise forms.ValidationError(titular_conflict_error_message(titular_elsewhere))

        cleaned["extra_days"] = extra_days
        return cleaned

    def _apply_times_and_relief(self, obj: ShiftAssignment) -> None:
        shift_type = self.cleaned_data["shift_type"]
        if shift_type == self.SHIFT_TYPE_DAY:
            obj.start_time = time(6, 0)
            obj.end_time = time(18, 0)
            incoming_date = obj.shift_date
            incoming_start = time(18, 0)
        else:
            obj.start_time = time(18, 0)
            obj.end_time = time(6, 0)
            incoming_date = obj.shift_date + timedelta(days=1)
            incoming_start = time(6, 0)
        obj.relieved_by = ShiftAssignment.objects.filter(
            site=obj.site,
            shift_date=incoming_date,
            start_time=incoming_start,
        ).first()

    def _ensure_fixed_post(self, obj: ShiftAssignment) -> None:
        shift_type = (
            FixedPost.ShiftType.DAY
            if obj.start_time == time(6, 0)
            else FixedPost.ShiftType.NIGHT
        )
        already_titular = FixedPost.objects.filter(
            site=obj.site,
            shift_type=shift_type,
            is_active=True,
            titular_guard=obj.guard,
        ).exists()
        if already_titular:
            return
        required = obj.site.staff_required_for_shift(shift_type)
        active_count = FixedPost.objects.filter(
            site=obj.site,
            shift_type=shift_type,
            is_active=True,
        ).count()
        if active_count >= required:
            raise forms.ValidationError(
                (
                    f"Effectif titulaire déjà complet ({required}) pour ce site en "
                    f"{'jour' if shift_type == FixedPost.ShiftType.DAY else 'nuit'}."
                )
            )
        FixedPost.objects.create(
            site=obj.site,
            shift_type=shift_type,
            titular_guard=obj.guard,
            is_active=True,
        )

    def save(self, commit=True):
        if not self.for_create:
            obj = super().save(commit=False)
            self._apply_times_and_relief(obj)
            if commit:
                obj.save()
            return obj

        mode = self.cleaned_data.get("planning_mode", self.MODE_PLANIFIER)
        if mode == self.MODE_EXTRA:
            guard = self.cleaned_data["guard"]
            site = self.cleaned_data["site"]
            shift_date = self.cleaned_data["shift_date"]
            shift_type = self.cleaned_data["shift_type"]
            extra_days = self.cleaned_data["extra_days"]
            start_time, end_time = self._slot_times(shift_type)
            first = None
            for offset in range(extra_days):
                day = shift_date + timedelta(days=offset)
                assignment = ShiftAssignment(
                    guard=guard,
                    site=site,
                    shift_date=day,
                    start_time=start_time,
                    end_time=end_time,
                    status=ShiftAssignment.Status.EXTRA,
                    relieved_by=None,
                )
                if commit:
                    assignment.save()
                if first is None:
                    first = assignment
            return first

        obj = super().save(commit=False)
        obj.status = ShiftAssignment.Status.SCHEDULED
        self._apply_times_and_relief(obj)
        if commit:
            obj.save()
            if self.cleaned_data.get("create_fixed_post"):
                self._ensure_fixed_post(obj)
        return obj


class AdminFcmTokenForm(forms.ModelForm):
    """Token FCM pour recevoir les alertes sur le téléphone (compte admin connecté)."""

    class Meta:
        model = User
        fields = ["fcm_token"]
        labels = {"fcm_token": "Token FCM de votre appareil"}
        widgets = {
            "fcm_token": forms.Textarea(
                attrs={
                    "class": _CTRL,
                    "rows": 4,
                    "placeholder": "Collez ici le token renvoyé par l’app mobile admin ou Firebase…",
                }
            ),
        }


class DispatchForm(forms.Form):
    assignment = AssignmentChoiceField(
        queryset=ShiftAssignment.objects.none(),
        label="Affectation",
        empty_label="Choisir une affectation…",
    )
    replacement_guard = GuardChoiceField(
        queryset=User.objects.filter(role=User.Role.VIGILE).order_by("username"),
        label="Vigile remplaçant",
        empty_label="Choisir un vigile…",
    )

    def clean(self):
        cleaned = super().clean()
        assignment = cleaned.get("assignment")
        replacement = cleaned.get("replacement_guard")
        if not (assignment and replacement):
            return cleaned
        conflict = find_assignment_conflict_on_other_site(
            guard_id=replacement.pk,
            site_id=assignment.site_id,
            shift_date=assignment.shift_date,
            start_time=assignment.start_time,
            exclude_assignment_id=assignment.pk,
        )
        if conflict:
            raise forms.ValidationError(
                {"replacement_guard": conflict_error_message(conflict)}
            )
        return cleaned

    def __init__(self, *args, **kwargs):
        assignments_qs = kwargs.pop("assignments_qs", None)
        super().__init__(*args, **kwargs)
        if assignments_qs is not None:
            self.fields["assignment"].queryset = assignments_qs
        self.fields["assignment"].widget.attrs.setdefault("class", _SEL)
        self.fields["replacement_guard"].widget.attrs.setdefault("class", _SEL)
