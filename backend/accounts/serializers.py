from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name", "role", "phone_number", "profile_photo")
        read_only_fields = ("profile_photo",)


class FCMTokenSerializer(serializers.Serializer):
    """Token FCM pour notifications push (admins uniquement)."""

    fcm_token = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        max_length=4096,
    )
