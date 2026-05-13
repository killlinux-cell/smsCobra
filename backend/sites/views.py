from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAdminRole
from sites.models import Site
from sites.serializers import SiteSerializer


class AdminSiteListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    queryset = Site.objects.all().order_by("name")
    serializer_class = SiteSerializer


class AdminSiteDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    queryset = Site.objects.all()
    serializer_class = SiteSerializer
