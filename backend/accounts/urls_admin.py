from django.urls import path

from .views_admin import AdminVigileListCreateView

urlpatterns = [
    path("", AdminVigileListCreateView.as_view(), name="admin-vigiles-api"),
]
