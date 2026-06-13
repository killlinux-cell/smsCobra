from django.urls import path

from .views import (
    AckAlertView,
    AckReplacementAssignmentView,
    AdminVigilesListView,
    AlertListView,
    DispatchCandidatesView,
    DispatchReplacementView,
    LiveStatusView,
    ReplacementNeededListView,
    TodayAssignmentsDispatchView,
)

urlpatterns = [
    path("live-status", LiveStatusView.as_view(), name="live-status"),
    path("replacement-needed", ReplacementNeededListView.as_view(), name="replacement-needed"),
    path(
        "replacement-needed/<int:assignment_id>/ack",
        AckReplacementAssignmentView.as_view(),
        name="replacement-needed-ack",
    ),
    path("", AlertListView.as_view(), name="alerts-list"),
    path("<int:alert_id>/ack", AckAlertView.as_view(), name="alerts-ack"),
    path("dispatch", DispatchReplacementView.as_view(), name="dispatch"),
    path("dispatch-candidates", DispatchCandidatesView.as_view(), name="dispatch-candidates"),
    path("today-assignments", TodayAssignmentsDispatchView.as_view(), name="alerts-today-assignments"),
    path("vigiles", AdminVigilesListView.as_view(), name="alerts-vigiles"),
]
