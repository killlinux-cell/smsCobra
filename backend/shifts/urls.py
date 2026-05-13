from django.urls import path
from .views import TodayAssignmentsView

urlpatterns = [
    path("today", TodayAssignmentsView.as_view(), name="assignments-today"),
]
