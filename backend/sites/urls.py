from django.urls import path

from .views import AdminSiteDetailView, AdminSiteListCreateView

urlpatterns = [
    path("", AdminSiteListCreateView.as_view(), name="admin-sites-list"),
    path("<int:pk>/", AdminSiteDetailView.as_view(), name="admin-sites-detail"),
]
