from django.urls import path

from .activity_feed import ActivityFeedView
from .views import ReportListView

urlpatterns = [
    path("activity/", ActivityFeedView.as_view(), name="activity-feed"),
    path("", ReportListView.as_view(), name="reports"),
]
