import secrets
from datetime import datetime, timedelta, time

from django import forms

from accounts.models import ControllerSiteAssignment, User
from shifts.models import FixedPost, ShiftAssignment
from sites.models import Site

_CTRL = "form-control"
_SEL = "form-select"


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
            "timezone",
            "expected_start_time",
            "expected_end_time",
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
            "timezone": "Fuseau horaire",
            "expected_start_time": "Heure de prise de service attendue",
            "expected_end_time": "Heure de fin de service attendue",
            "late_tolerance_minutes": "Tolérance de retard (prise de service, minutes)",
            "relief_late_alert_minutes": "Alerte releve non arrive (minutes apres heure prevue)",
            "latitude": "Latitude",
            "longitude": "Longitude",
            "geofence_radius_meters": "Rayon géofence (mètres)",
            "is_active": "Site actif",
        }
        widgets = {
            "name": forms.TextInput(attrs={"class": _CTRL}),
            "address": forms.TextInput(attrs={"class": _CTRL}),
            "timezone": forms.TextInput(attrs={"class": _CTRL}),
            "expected_start_time": forms.TimeInput(attrs={"class": _CTRL, "type": "time"}),
            "expected_end_time": forms.TimeInput(attrs={"class": _CTRL, "type": "time"}),
            "late_tolerance_minutes": forms.NumberInput(attrs={"class": _CTRL}),
            "relief_late_alert_minutes": forms.NumberInput(attrs={"class": _CTRL}),
            "latitude": forms.NumberInput(attrs={"class": _CTRL, "step": "any"}),
            "longitude": forms.NumberInput(attrs={"class": _CTRL, "step": "any"}),
            "geofence_radius_meters": forms.NumberInput(attrs={"class": _CTRL}),
            "geofence_gps_margin_meters": forms.NumberInput(attrs={"class": _CTRL}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


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
        widget=forms.SelectMultiple(attrs={"class": _SEL, "size": 8}),
        help_text="Sites sur lesquels ce contrôleur peut enregistrer son passage.",
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


class VigileUpdateForm(forms.ModelForm):
    """Mise à jour d'un vigile depuis le tableau de bord (fiche détail)."""

    new_password1 = forms.CharField(
        label="Nouveau mot de passe (facultatif)",
        required=False,
        widget=forms.PasswordInput(attrs={"class": _CTRL, "autocomplete": "new-password"}),
        help_text="Laissez vide pour ne pas modifier. Au moins 8 caractères si renseigné.",
    )
    new_password2 = forms.CharField(
        label="Confirmer le mot de passe",
        required=False,
        widget=forms.PasswordInput(attrs={"class": _CTRL, "autocomplete": "new-password"}),
    )

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

    def clean_username(self):
        u = (self.cleaned_data.get("username") or "").strip()
        if not u:
            raise forms.ValidationError("L'identifiant est obligatoire.")
        if User.objects.filter(username=u).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Cet identifiant est déjà utilisé.")
        return u

    def clean(self):
        cleaned = super().clean()
        p1 = (cleaned.get("new_password1") or "").strip()
        p2 = (cleaned.get("new_password2") or "").strip()
        if p1 or p2:
            if p1 != p2:
                self.add_error("new_password2", "Les mots de passe ne correspondent pas.")
            elif len(p1) < 8:
                self.add_error("new_password1", "Au moins 8 caractères.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        p1 = (self.cleaned_data.get("new_password1") or "").strip()
        if p1:
            user.set_password(p1)
        if commit:
            user.save()
        return user


class ShiftAssignmentForm(forms.ModelForm):
    SHIFT_TYPE_DAY = "day"
    SHIFT_TYPE_NIGHT = "night"

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
        fields = ["guard", "site", "shift_date", "shift_type", "status"]
        labels = {
            "guard": "Vigile",
            "site": "Site",
            "shift_date": "Date",
            "status": "Statut",
        }
        widgets = {
            "guard": forms.Select(attrs={"class": _SEL}),
            "site": forms.Select(attrs={"class": _SEL}),
            "shift_date": forms.DateInput(attrs={"class": _CTRL, "type": "date"}),
            "status": forms.Select(attrs={"class": _SEL}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["guard"].queryset = User.objects.filter(role=User.Role.VIGILE).order_by("username")
        self.fields["guard"] = GuardChoiceField(
            queryset=self.fields["guard"].queryset,
            label=self.fields["guard"].label,
        )
        self.fields["guard"].widget.attrs.setdefault("class", _SEL)
        self.fields["site"].queryset = Site.objects.filter(is_active=True).order_by("name")
        if self.instance and self.instance.pk:
            if self.instance.start_time == time(6, 0):
                self.fields["shift_type"].initial = self.SHIFT_TYPE_DAY
            elif self.instance.start_time == time(18, 0):
                self.fields["shift_type"].initial = self.SHIFT_TYPE_NIGHT

    def clean(self):
        cleaned = super().clean()
        site = cleaned.get("site")
        guard = cleaned.get("guard")
        shift_date = cleaned.get("shift_date")
        shift_type = cleaned.get("shift_type")
        if not (site and guard and shift_date and shift_type):
            return cleaned

        if shift_type == self.SHIFT_TYPE_DAY:
            start_time = time(6, 0)
            end_time = time(18, 0)
        else:
            start_time = time(18, 0)
            end_time = time(6, 0)

        cleaned["start_time"] = start_time
        cleaned["end_time"] = end_time

        same_slot = ShiftAssignment.objects.filter(
            site=site,
            shift_date=shift_date,
            start_time=start_time,
        )
        if self.instance.pk:
            same_slot = same_slot.exclude(pk=self.instance.pk)
        if same_slot.exists():
            raise forms.ValidationError("Ce poste (jour/nuit) est deja attribue pour ce site et cette date.")

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
                "Ce vigile est deja affecte au poste oppose autour de cette passation. Choisissez un autre vigile."
            )

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
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
        if commit:
            obj.save()
            if self.cleaned_data.get("create_fixed_post"):
                shift_type = (
                    FixedPost.ShiftType.DAY
                    if obj.start_time == time(6, 0)
                    else FixedPost.ShiftType.NIGHT
                )
                existing = (
                    FixedPost.objects.filter(site=obj.site, shift_type=shift_type, is_active=True)
                    .exclude(titular_guard=obj.guard)
                    .first()
                )
                if existing:
                    existing.is_active = False
                    existing.save(update_fields=["is_active"])
                FixedPost.objects.update_or_create(
                    site=obj.site,
                    shift_type=shift_type,
                    is_active=True,
                    defaults={
                        "titular_guard": obj.guard,
                    },
                )
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

    def __init__(self, *args, **kwargs):
        assignments_qs = kwargs.pop("assignments_qs", None)
        super().__init__(*args, **kwargs)
        if assignments_qs is not None:
            self.fields["assignment"].queryset = assignments_qs
        self.fields["assignment"].widget.attrs.setdefault("class", _SEL)
        self.fields["replacement_guard"].widget.attrs.setdefault("class", _SEL)
