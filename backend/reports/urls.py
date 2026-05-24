from django.urls import path

from .activity_feed import ActivityFeedView
from .controller_visit_views import ControllerVisitReportView
from .views import ReportListView

urlpatterns = [
    path("activity/", ActivityFeedView.as_view(), name="activity-feed"),
    path("controller-visits/", ControllerVisitReportView.as_view(), name="controller-visits"),
    path("", ReportListView.as_view(), name="reports"),
]
