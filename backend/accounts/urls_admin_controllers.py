from django.urls import path

from .views_admin import AdminControllerDetailView, AdminControllerListCreateView

urlpatterns = [
    path("", AdminControllerListCreateView.as_view(), name="admin-controllers-api"),
    path("<int:pk>/", AdminControllerDetailView.as_view(), name="admin-controller-detail-api"),
]
