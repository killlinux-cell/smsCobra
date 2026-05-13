from django.urls import path

from .views import EntrySitesView, FCMTokenView, MeView

urlpatterns = [
    path("me", MeView.as_view(), name="me"),
    path("me/fcm-token", FCMTokenView.as_view(), name="me-fcm-token"),
    path("entry/sites", EntrySitesView.as_view(), name="entry-sites"),
]
