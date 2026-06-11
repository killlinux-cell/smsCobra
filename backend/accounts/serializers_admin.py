"""Serializers API admin mobile / outils (sites & vigiles)."""

import secrets

from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.face_profile import (
    enrollment_photo_error_message,
    refresh_face_embedding_if_vigile,
    validate_profile_photo_upload,
)

User = get_user_model()


def generate_vigile_username() -> str:
    max_num = 0
    for value in User.objects.filter(role=User.Role.VIGILE).values_list("username", flat=True):
        if value and value.startswith("VIR-"):
            suffix = value[4:]
            if suffix.isdigit():
                max_num = max(max_num, int(suffix))
    return f"VIR-{max_num + 1:03d}"


class VigileAdminSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    profile_photo = serializers.SerializerMethodField()
    id_document = serializers.SerializerMethodField()
    id_document_verso = serializers.SerializerMethodField()

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
        ]

    def get_display_name(self, obj: User) -> str:
        return obj.display_name

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
        refresh_face_embedding_if_vigile(user, photo_updated=True)
        return user
