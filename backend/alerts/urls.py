from django.urls import path

from .views import (
    AckAlertView,
    AdminVigilesListView,
    AlertListView,
    DispatchReplacementView,
    LiveStatusView,
    TodayAssignmentsDispatchView,
)

urlpatterns = [
    path("live-status", LiveStatusView.as_view(), name="live-status"),
    path("", AlertListView.as_view(), name="alerts-list"),
    path("<int:alert_id>/ack", AckAlertView.as_view(), name="alerts-ack"),
    path("dispatch", DispatchReplacementView.as_view(), name="dispatch"),
    path("today-assignments", TodayAssignmentsDispatchView.as_view(), name="alerts-today-assignments"),
    path("vigiles", AdminVigilesListView.as_view(), name="alerts-vigiles"),
]
