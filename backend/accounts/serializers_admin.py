"""Serializers API admin mobile / outils (sites, vigiles & contrôleurs)."""

import secrets

from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.face_profile import (
    enrollment_photo_error_message,
    refresh_face_embedding_if_vigile,
    validate_profile_photo_upload,
)
from accounts.models import ControllerSiteAssignment
from sites.models import Site

User = get_user_model()


def generate_vigile_username() -> str:
    max_num = 0
    for value in User.objects.filter(role=User.Role.VIGILE).values_list("username", flat=True):
        if value and value.startswith("VIR-"):
            suffix = value[4:]
            if suffix.isdigit():
                max_num = max(max_num, int(suffix))
    return f"VIR-{max_num + 1:03d}"


def generate_controller_username() -> str:
    max_num = 0
    for value in User.objects.filter(role=User.Role.CONTROLEUR).values_list("username", flat=True):
        if value and value.startswith("CTR-"):
            suffix = value[4:]
            if suffix.isdigit():
                max_num = max(max_num, int(suffix))
    return f"CTR-{max_num + 1:03d}"


def coerce_site_ids(value) -> list[int]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [int(v) for v in value if str(v).strip()]
    raw = str(value).strip()
    if not raw:
        return []
    if raw.startswith("["):
        import json

        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise serializers.ValidationError("site_ids invalide.")
        return [int(v) for v in parsed]
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            ids.append(int(part))
    return ids


def sync_controller_site_assignments(controller: User, site_ids: list[int]) -> None:
    selected_ids = set(site_ids)
    if selected_ids:
        valid_ids = set(
            Site.objects.filter(id__in=selected_ids, is_active=True).values_list("id", flat=True)
        )
        missing = selected_ids - valid_ids
        if missing:
            raise serializers.ValidationError(
                {"site_ids": f"Site(s) introuvable(s) ou inactif(s) : {sorted(missing)}"}
            )
        selected_ids = valid_ids
    for site_id in selected_ids:
        ControllerSiteAssignment.objects.update_or_create(
            controller=controller,
            site_id=site_id,
            defaults={"is_active": True},
        )
    ControllerSiteAssignment.objects.filter(controller=controller).exclude(
        site_id__in=selected_ids
    ).delete()


class CommaSeparatedIntListField(serializers.Field):
    """Accepte 1,2,3 ou une liste (multipart / JSON)."""

    def to_internal_value(self, data):
        try:
            return coerce_site_ids(data)
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError("Liste de sites invalide.") from exc

    def to_representation(self, value):
        return list(value or [])


class VigileAdminSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    profile_photo = serializers.SerializerMethodField()
    id_document = serializers.SerializerMethodField()
    id_document_verso = serializers.SerializerMethodField()
    face_enrollment_ok = serializers.SerializerMethodField()
    placement = serializers.SerializerMethodField()
    date_joined = serializers.DateTimeField(read_only=True)
    last_login = serializers.DateTimeField(read_only=True)
    role = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "domicile",
            "is_active",
            "aval",
            "date_integration",
            "height_cm",
            "education_level",
            "display_name",
            "profile_photo",
            "id_document",
            "id_document_verso",
            "face_enrollment_ok",
            "is_active_on_duty",
            "placement",
            "date_joined",
            "last_login",
            "role",
        ]

    def get_placement(self, obj: User) -> dict:
        from webadmin.vigile_placement import build_vigile_placement

        return build_vigile_placement(obj)

    def get_display_name(self, obj: User) -> str:
        return obj.display_name

    def get_face_enrollment_ok(self, obj: User) -> bool:
        return bool(obj.profile_photo and obj.face_embedding)

    def get_profile_photo(self, obj: User):
        if not obj.profile_photo:
            return None
        request = self.context.get("request")
        url = obj.profile_photo.url
        if request:
            return request.build_absolute_uri(url)
        return url

    def get_id_document(self, obj: User):
        return self._file_url(obj.id_document)

    def get_id_document_verso(self, obj: User):
        return self._file_url(obj.id_document_verso)

    def _file_url(self, file_field):
        if not file_field:
            return None
        request = self.context.get("request")
        url = file_field.url
        if request:
            return request.build_absolute_uri(url)
        return url


class VigileCreateSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password_confirm = serializers.CharField(write_only=True, required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    domicile = serializers.CharField(required=False, allow_blank=True)
    aval = serializers.CharField(required=False, allow_blank=True)
    date_integration = serializers.DateField(required=False, allow_null=True)
    height_cm = serializers.IntegerField(required=False, allow_null=True, min_value=100, max_value=250)
    education_level = serializers.ChoiceField(
        choices=User.EducationLevel.choices,
        required=False,
        allow_blank=True,
    )
    id_document = serializers.FileField(required=False, allow_null=True)
    id_document_verso = serializers.FileField(required=False, allow_null=True)
    profile_photo = serializers.ImageField()

    def validate(self, attrs):
        password = (attrs.get("password") or "").strip()
        password_confirm = (attrs.get("password_confirm") or "").strip()
        if password or password_confirm:
            if password != password_confirm:
                raise serializers.ValidationError(
                    {"password_confirm": "Les mots de passe ne correspondent pas."}
                )
            if len(password) < 8:
                raise serializers.ValidationError(
                    {"password": "Au moins 8 caractères."}
                )
        return attrs

    def validate_username(self, value):
        v = (value or "").strip()
        if not v:
            return ""
        if User.objects.filter(username=v).exists():
            raise serializers.ValidationError("Cet identifiant est deja utilise.")
        return v

    def validate_profile_photo(self, value):
        ok, fail_code = validate_profile_photo_upload(value)
        if not ok:
            raise serializers.ValidationError(enrollment_photo_error_message(fail_code))
        try:
            value.seek(0)
        except (AttributeError, OSError):
            pass
        return value

    def create(self, validated_data):
        vd = validated_data.copy()
        vd.pop("password_confirm", None)
        pwd = (vd.pop("password", "") or "").strip()
        photo = vd.pop("profile_photo")
        id_doc = vd.pop("id_document", None)
        id_doc_verso = vd.pop("id_document_verso", None)
        date_int = vd.pop("date_integration", None)
        aval = (vd.pop("aval", None) or "").strip()
        domicile = (vd.pop("domicile", None) or "").strip()
        height_cm = vd.pop("height_cm", None)
        education_level = (vd.pop("education_level", None) or "").strip()
        username = (vd.get("username") or "").strip() or generate_vigile_username()
        while User.objects.filter(username=username).exists():
            username = generate_vigile_username()
        user = User(
            username=username,
            role=User.Role.VIGILE,
            first_name=(vd.get("first_name") or "").strip(),
            last_name=(vd.get("last_name") or "").strip(),
            email=(vd.get("email") or "").strip(),
            phone_number=(vd.get("phone_number") or "").strip(),
            domicile=domicile,
            profile_photo=photo,
            aval=aval,
            date_integration=date_int,
            height_cm=height_cm,
            education_level=education_level,
        )
        if id_doc:
            user.id_document = id_doc
        if id_doc_verso:
            user.id_document_verso = id_doc_verso
        # Connexion vigile principalement faciale : mot de passe optionnel.
        # Si absent, on en crée un aléatoire robuste pour garder le compte sécurisé.
        user.set_password(pwd or secrets.token_urlsafe(24))
        user.save()
        try:
            refresh_face_embedding_if_vigile(user, photo_updated=True)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Empreinte faciale non calculée à la création API du vigile %s",
                user.username,
            )
        return user


class VigileUpdateSerializer(serializers.ModelSerializer):
    profile_photo = serializers.ImageField(required=False, allow_null=True)
    id_document = serializers.FileField(required=False, allow_null=True)
    id_document_verso = serializers.FileField(required=False, allow_null=True)

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
            "id_document_verso",
            "is_active",
            "is_active_on_duty",
        ]
        extra_kwargs = {
            "username": {"required": False},
            "first_name": {"required": False, "allow_blank": True},
            "last_name": {"required": False, "allow_blank": True},
            "email": {"required": False, "allow_blank": True},
            "phone_number": {"required": False, "allow_blank": True},
            "domicile": {"required": False, "allow_blank": True},
            "aval": {"required": False, "allow_blank": True},
            "date_integration": {"required": False, "allow_null": True},
            "height_cm": {"required": False, "allow_null": True},
            "education_level": {"required": False, "allow_blank": True},
        }

    def validate_username(self, value):
        u = (value or "").strip()
        if not u:
            raise serializers.ValidationError("L'identifiant est obligatoire.")
        qs = User.objects.filter(username=u)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Cet identifiant est déjà utilisé.")
        return u

    def validate_profile_photo(self, value):
        if not value:
            return value
        ok, fail_code = validate_profile_photo_upload(value)
        if not ok:
            raise serializers.ValidationError(enrollment_photo_error_message(fail_code))
        try:
            value.seek(0)
        except (AttributeError, OSError):
            pass
        return value

    def update(self, instance, validated_data):
        photo = validated_data.pop("profile_photo", None)
        id_doc = validated_data.pop("id_document", None)
        id_doc_verso = validated_data.pop("id_document_verso", None)
        photo_updated = photo is not None
        for field, value in validated_data.items():
            if field == "education_level" and not value:
                value = ""
            if field in ("first_name", "last_name", "email", "phone_number", "domicile", "aval"):
                value = (value or "").strip()
            setattr(instance, field, value)
        if photo_updated:
            instance.profile_photo = photo
        if id_doc is not None:
            instance.id_document = id_doc
        if id_doc_verso is not None:
            instance.id_document_verso = id_doc_verso
        instance.save()
        try:
            refresh_face_embedding_if_vigile(instance, photo_updated=photo_updated)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Empreinte faciale non calculée à la mise à jour API du vigile %s",
                instance.username,
            )
        return instance


class ControllerAdminSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    profile_photo = serializers.SerializerMethodField()
    portrait_ok = serializers.SerializerMethodField()
    authorized_site_ids = serializers.SerializerMethodField()
    authorized_sites = serializers.SerializerMethodField()
    date_joined = serializers.DateTimeField(read_only=True)
    last_login = serializers.DateTimeField(read_only=True)
    role = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "is_active",
            "display_name",
            "profile_photo",
            "portrait_ok",
            "authorized_site_ids",
            "authorized_sites",
            "date_joined",
            "last_login",
            "role",
        ]

    def get_display_name(self, obj: User) -> str:
        return obj.display_name

    def get_portrait_ok(self, obj: User) -> bool:
        return bool(obj.profile_photo)

    def get_profile_photo(self, obj: User):
        if not obj.profile_photo:
            return None
        request = self.context.get("request")
        url = obj.profile_photo.url
        if request:
            return request.build_absolute_uri(url)
        return url

    def get_authorized_site_ids(self, obj: User) -> list[int]:
        return list(
            ControllerSiteAssignment.objects.filter(controller=obj, is_active=True)
            .order_by("site__name")
            .values_list("site_id", flat=True)
        )

    def get_authorized_sites(self, obj: User) -> list[dict]:
        rows = (
            ControllerSiteAssignment.objects.filter(controller=obj, is_active=True)
            .select_related("site")
            .order_by("site__name")
        )
        return [{"id": a.site_id, "name": a.site.name} for a in rows if a.site_id]


class ControllerCreateSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    profile_photo = serializers.ImageField()
    site_ids = CommaSeparatedIntListField(required=False)

    def validate_username(self, value):
        v = (value or "").strip()
        if not v:
            return ""
        if User.objects.filter(username=v).exists():
            raise serializers.ValidationError("Cet identifiant est deja utilise.")
        return v

    def validate_profile_photo(self, value):
        ok, fail_code = validate_profile_photo_upload(value)
        if not ok:
            raise serializers.ValidationError(enrollment_photo_error_message(fail_code))
        try:
            value.seek(0)
        except (AttributeError, OSError):
            pass
        return value

    def create(self, validated_data):
        site_ids = validated_data.pop("site_ids", [])
        photo = validated_data.pop("profile_photo")
        username = (validated_data.get("username") or "").strip() or generate_controller_username()
        while User.objects.filter(username=username).exists():
            username = generate_controller_username()
        user = User(
            username=username,
            role=User.Role.CONTROLEUR,
            first_name=(validated_data.get("first_name") or "").strip(),
            last_name=(validated_data.get("last_name") or "").strip(),
            email=(validated_data.get("email") or "").strip(),
            phone_number=(validated_data.get("phone_number") or "").strip(),
            profile_photo=photo,
        )
        user.set_password(secrets.token_urlsafe(24))
        user.save()
        sync_controller_site_assignments(user, site_ids)
        return user


class ControllerUpdateSerializer(serializers.ModelSerializer):
    profile_photo = serializers.ImageField(required=False, allow_null=True)
    site_ids = CommaSeparatedIntListField(required=False)

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "profile_photo",
            "is_active",
            "site_ids",
        ]
        extra_kwargs = {
            "username": {"required": False},
            "first_name": {"required": False, "allow_blank": True},
            "last_name": {"required": False, "allow_blank": True},
            "email": {"required": False, "allow_blank": True},
            "phone_number": {"required": False, "allow_blank": True},
        }

    def validate_username(self, value):
        u = (value or "").strip()
        if not u:
            raise serializers.ValidationError("L'identifiant est obligatoire.")
        qs = User.objects.filter(username=u)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Cet identifiant est deja utilise.")
        return u

    def validate_profile_photo(self, value):
        if not value:
            return value
        ok, fail_code = validate_profile_photo_upload(value)
        if not ok:
            raise serializers.ValidationError(enrollment_photo_error_message(fail_code))
        try:
            value.seek(0)
        except (AttributeError, OSError):
            pass
        return value

    def update(self, instance, validated_data):
        site_ids = validated_data.pop("site_ids", None)
        photo = validated_data.pop("profile_photo", None)
        for field, value in validated_data.items():
            if field in ("first_name", "last_name", "email", "phone_number"):
                value = (value or "").strip()
            setattr(instance, field, value)
        if photo is not None:
            instance.profile_photo = photo
        instance.save()
        if site_ids is not None:
            sync_controller_site_assignments(instance, site_ids)
        return instance
