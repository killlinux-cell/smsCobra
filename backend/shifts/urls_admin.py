from django.urls import path

from shifts.views_admin import AdminAssignmentDetailView, AdminAssignmentListCreateView

urlpatterns = [
    path("", AdminAssignmentListCreateView.as_view(), name="admin-assignments-list"),
    path("<int:pk>/", AdminAssignmentDetailView.as_view(), name="admin-assignments-detail"),
]
