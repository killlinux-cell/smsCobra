from django.urls import path

from .views_admin import AdminVigileDetailView, AdminVigileListCreateView

urlpatterns = [
    path("", AdminVigileListCreateView.as_view(), name="admin-vigiles-api"),
    path("<int:pk>/", AdminVigileDetailView.as_view(), name="admin-vigile-detail-api"),
]
