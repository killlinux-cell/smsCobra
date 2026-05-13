from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsAdminRole
from accounts.serializers_admin import VigileAdminSerializer, VigileCreateSerializer


class AdminVigileListCreateView(generics.ListCreateAPIView):
    """Liste des vigiles (champs étendus) + création (multipart, comme le web)."""

    permission_classes = [IsAuthenticated, IsAdminRole]

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
