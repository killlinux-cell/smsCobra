from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsAdminRole
from accounts.serializers_admin import (
    VigileAdminSerializer,
    VigileCreateSerializer,
    VigileUpdateSerializer,
)


class AdminVigileListCreateView(generics.ListCreateAPIView):
    """Liste des vigiles (champs étendus) + création (multipart, comme le web)."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return User.objects.filter(role=User.Role.VIGILE).order_by("username")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return VigileCreateSerializer
        return VigileAdminSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        out = VigileAdminSerializer(user, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)


class AdminVigileDetailView(generics.RetrieveUpdateAPIView):
    """Fiche vigile + mise à jour (JSON ou multipart avec photo)."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    lookup_url_kwarg = "pk"

    def get_queryset(self):
        return User.objects.filter(role=User.Role.VIGILE)

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return VigileUpdateSerializer
        return VigileAdminSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        out = VigileAdminSerializer(user, context={"request": request})
        return Response(out.data)
